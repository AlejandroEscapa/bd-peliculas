"""Motor de recomendaciones explicable sobre tu propio catálogo.

No hay filtrado colaborativo: con un solo usuario no hay señal de otros que
aprender, y el caso es privado por diseño. Todo lo que sale de aquí sale de
**tus notas** y de **los hechos de los títulos**, y cada título recomendado
viene con **por qué**.

Cuatro capas, de la más simple a la más fina:

  A. Afinidad: por cada faceta (género, director, actor, década, país) mide el
     *lift*: tu media en esa faceta menos tu media global. Positivo = te
     gusta; negativo = te sale flojo.
  B. Antiperfil: facetas donde IMDb te gana de forma consistente. Penalizan.
  C. Reglas: si el pendiente comparte saga con algo que valoraste, sube.
  D. Similitud textual: TF-IDF con hashing trick + coseno sobre las sinopsis.
     Dice "se parece a X" en términos concretos, no opacos.

Todo es determinista: sin azar, sin red y sin float dependiente del orden de
inserción. La misma base da siempre la misma lista.

El motor calcula; el panel enseña. Eso mantiene la regla del repo: el panel
es un HTML estático generado, y el cálculo vive en Python donde se puede
testear.
"""
from __future__ import annotations

import math
import re
import sqlite3
import unicodedata
import zlib
from collections import Counter
from pathlib import Path

from .db import get_connection

# Una faceta con menos muestras es ruido, no una preferencia.
MIN_MUESTRAS = 2

# Dimensión del hashing trick (TF-IDF disperso, sin dependencias).
VECTORES = 4096

# Peso de cada faceta en el encaje. El director pesa más que el género porque
# une el interés por el tema con la confianza en el oficio; el país y la
# década apenas sirven para desempatar.
PESOS = {
    "genero": 1.0,
    "director": 1.2,
    "actor": 0.8,
    "decada": 0.5,
    "pais": 0.4,
}

# Un promedio de IMDb que te gana por 1 punto o más es aviso de decepción.
UMBRAL_ANTIPROFIL = -1.0

# Tamaño de efecto mínimo para que una faceta cuente como preferencia.
# Media punto en una escala de 1 a 10 es la diferencia entre "me gusta" y
# "no me disgusta": no cambia lo que vas a ver, así que no merece ser un
# motivo. Con 0.2 el panel repetía "el género Drama te sale alto: 7.8
# frente a tu 7.5 global" en casi todas las filas, que no informa de nada.
UMBRAL_LIFT = 0.5

# Cuánta evidencia pesa un lift. Un director con 2 títulos y +1.9 no puede
# pesar más que un género con 17 y +0.9: el lift se encoge por el tamaño de
# la muestra (lift * n / (n + K)).
PESO_EVIDENCIA = 4.0

# Coseno mínimo para decir "se parece a", y al menos dos términos en común.
# Los términos compartidos tienen que ser de contenido: la lista de stopwords
# quita pronombres y verbos genéricos, que si no emparejaban cualquier cosa
# ("his" era el término más "informativo" del catálogo entero).
UMBRAL_SIMILITUD = 0.12
MIN_TERMINOS_COMUNES = 2

# IMDb como desempate: poco peso, solo para ordenar títulos parecidos.
PESO_IMDB = 0.25

# Etiquetas legibles de cada faceta (para los motivos).
ETIQUETAS = {
    "genero": "género",
    "director": "director",
    "actor": "actor",
    "decada": "década",
    "pais": "país",
}

# Artículo y preposición correctos: "la década 2010", "con el director X".
ARTICULO = {
    "genero": "el", "director": "el", "actor": "el", "decada": "la", "pais": "el",
}
PREPOSICION = {
    "genero": "En", "director": "Con", "actor": "Con", "decada": "En", "pais": "En",
}

STOPWORDS = frozenset("""
a al algo algun alguna alguno algunos ante antes aqui asi aun aunque bajo bien cada
como con contra cual cuando de del desde donde dos el ella ellas ellos en entre era
eres es esa esas ese eso estos esta estan estas este esto estos fue fueron ha habia
han hasta hay la las le les lo los mas me mi mis mucho muchos muy nada ni no nos
nuestra nuestro o os otra otro para pero poco por porque que quien se sea segun ser
si sin sobre solo son su sus tambien tan tanto te tiene tienen todo todos tu tus
un una uno unos y ya yo
the a an and are as at be but by for from has have he in is it its of on or that the
this to was were will with
his her hers their theirs they them this that these those there here who whom whose
which what when where why how while into onto upon with without within across through
during before after above below under over again further once all any both each few
more most other another some such only own same so than then too very just now one
two three four five many much shall can could would should may might must will do
does did done have has had having been being get gets got make makes made take takes
taken come comes came go goes went see sees saw know knows knew think thinks thought
say says said want wants look looks find finds tell tells ask asks work works use
uses used feel feels give gives gave become becomes lives live explores explore
tracks track down out up off near far first last next previous new old young
man woman boy girl people person family friend home house city street road car
money war hero villain father mother son daughter brother sister husband wife boss
enemy partner team group member leader king queen battle army peace love life death
men women boys girls children families friends homes houses cities streets cars teams
groups members leaders enemies partners bosses fathers mothers sons daughters
brothers sisters husbands wives wars heroes villains kings queens armies
""".split())

_RE_TOKEN = re.compile(r"[a-z0-9]+")


# ---------------------------------------------------------------- utilidades


def _media(valores) -> float:
    vals = [v for v in valores if v is not None]
    return sum(vals) / len(vals) if vals else 0.0


def _texto_sin_acentos(texto: str) -> str:
    plano = unicodedata.normalize("NFKD", texto.lower())
    return "".join(c for c in plano if not unicodedata.combining(c))


def _tokens(texto: str) -> list[str]:
    """Palabras útiles de un texto: sin acentos, sin ruido, sin stopwords."""
    if not texto:
        return []
    limpio = _texto_sin_acentos(texto)
    salida = []
    for palabra in _RE_TOKEN.findall(limpio):
        if len(palabra) < 3 or palabra in STOPWORDS or palabra.isdigit():
            continue
        salida.append(palabra)
    return salida


def _indice_token(token: str) -> int:
    """Hash estable (crc32): `hash()` de Python cambia entre procesos."""
    return zlib.crc32(token.encode("utf-8")) % VECTORES


# ------------------------------------------------------------------ lectura


def _datos(conn: sqlite3.Connection) -> tuple[dict, list, dict]:
    """Devuelve (valoradas, pendientes, meta) con meta[tt] = hechos del título."""
    valoradas: dict[str, int] = {}
    pendientes: list[str] = []
    meta: dict[str, dict] = {}

    for r in conn.execute(
            "SELECT t.tt, t.title_es, t.original_title, t.year, t.imdb_rating, "
            "       t.synopsis, u.my_rating "
            "FROM titles t JOIN user_state u ON u.tt = t.tt"):
        tt = r["tt"]
        meta[tt] = {
            "titulo": r["title_es"] or r["original_title"] or tt,
            "year": r["year"],
            "imdb": r["imdb_rating"],
            "sinopsis": r["synopsis"] or "",
        }
        if r["my_rating"] is None:
            pendientes.append(tt)
        else:
            valoradas[tt] = r["my_rating"]

    return valoradas, pendientes, meta


def _facetas_por_tt(conn: sqlite3.Connection) -> dict[str, dict[str, set[str]]]:
    """tt -> faceta -> valores que tiene ese título."""
    facetas: dict[str, dict[str, set[str]]] = {}

    def anota(tt: str, faceta: str, valor) -> None:
        if valor is None:
            return
        facetas.setdefault(tt, {}).setdefault(faceta, set()).add(str(valor))

    for r in conn.execute("SELECT tt, genre FROM title_genres"):
        anota(r["tt"], "genero", r["genre"])
    for r in conn.execute(
            "SELECT c.tt, p.name FROM title_credits c JOIN people p ON p.id = c.person_id "
            "WHERE c.role = 'director'"):
        anota(r["tt"], "director", r["name"])
    for r in conn.execute(
            "SELECT c.tt, p.name FROM title_cast c JOIN people p ON p.id = c.person_id "
            "WHERE c.cast_order IS NOT NULL AND c.cast_order <= 3"):
        anota(r["tt"], "actor", r["name"])
    for r in conn.execute("SELECT tt, (year / 10) * 10 AS decada FROM titles "
                          "WHERE year IS NOT NULL"):
        anota(r["tt"], "decada", r["decada"])
    for r in conn.execute("SELECT tt, country_code FROM title_countries"):
        anota(r["tt"], "pais", r["country_code"])

    return facetas


def _colecciones(conn: sqlite3.Connection) -> dict[str, list[tuple[str, str]]]:
    """tt -> [(tt_otro, nombre_coleccion), ...] de las colecciones con saga."""
    saga: dict[str, list[tuple[str, str]]] = {}
    filas = conn.execute(
        "SELECT c.tt, c.collection_name, o.tt AS otro "
        "FROM title_collections c JOIN title_collections o "
        "  ON o.collection_id = c.collection_id AND o.tt <> c.tt "
        "WHERE c.collection_id IS NOT NULL "
        "ORDER BY c.collection_id, o.tt").fetchall()
    for r in filas:
        saga.setdefault(r["tt"], []).append((r["otro"], r["collection_name"] or "la saga"))
    return saga


# -------------------------------------------------------------------- perfil


def perfil(conn: sqlite3.Connection, min_muestras: int = MIN_MUESTRAS) -> dict:
    """Perfil de gusto: lift por faceta y el antiperfil de IMDb.

    Devuelve {"global": media global, "facetas": {faceta: {valor: {...}}},
              "antiperfil": [valores de faceta], "genero": {...}}.
    """
    valoradas, _, meta = _datos(conn)
    facetas = _facetas_por_tt(conn)
    if not valoradas:
        return {"global": 0.0, "facetas": {}, "antiperfil": [], "n_valoradas": 0}

    global_media = _media(valoradas.values())
    acum: dict[str, dict[str, dict]] = {}
    diffs: dict[str, dict[str, list]] = {}

    for tt, nota in valoradas.items():
        for faceta, valores in facetas.get(tt, {}).items():
            for valor in valores:
                slot = acum.setdefault(faceta, {}).setdefault(
                    valor, {"n": 0, "notas": [], "diff": []})
                slot["n"] += 1
                slot["notas"].append(nota)
                imdb = meta.get(tt, {}).get("imdb")
                if imdb is not None:
                    slot["diff"].append(nota - imdb)

    limpio: dict[str, dict[str, dict]] = {}
    antiprofil: list[str] = []
    for faceta, valores in acum.items():
        limpio[faceta] = {}
        for valor, slot in valores.items():
            if slot["n"] < min_muestras:
                continue
            media = _media(slot["notas"])
            diff = _media(slot["diff"])
            limpio[faceta][valor] = {
                "n": slot["n"],
                "media": round(media, 2),
                "lift": round(media - global_media, 2),
                "diff_imdb": round(diff, 2),
            }
            if diff <= UMBRAL_ANTIPROFIL:
                antiprofil.append(f"{faceta}:{valor}")

    return {
        "global": round(global_media, 2),
        "n_valoradas": len(valoradas),
        "facetas": limpio,
        "antiperfil": antiprofil,
    }


# ---------------------------------------------------------------- similitud


def indice_sinopsis(conn: sqlite3.Connection) -> tuple[dict[str, dict[int, float]], dict[int, float]]:
    """TF-IDF disperso de las sinopsis, con hashing crc32 (estable)."""
    docs: dict[str, list[str]] = {}
    for r in conn.execute("SELECT tt, synopsis FROM titles WHERE synopsis IS NOT NULL "
                          "AND synopsis <> ''"):
        tokens = _tokens(r["synopsis"])
        if tokens:
            docs[r["tt"]] = tokens
    if not docs:
        return {}, {}

    df: Counter = Counter()
    for tokens in docs.values():
        df.update({_indice_token(t) for t in tokens})
    n = len(docs)
    idf = {idx: math.log((n + 1) / (df[idx] + 1)) + 1.0 for idx in df}

    vectores: dict[str, dict[int, float]] = {}
    for tt, tokens in docs.items():
        conteo = Counter(_indice_token(t) for t in tokens)
        vec = {idx: (1 + math.log(c)) * idf.get(idx, 0.0) for idx, c in conteo.items()}
        norma = math.sqrt(sum(v * v for v in vec.values())) or 1.0
        vectores[tt] = {idx: v / norma for idx, v in vec.items()}
    return vectores, idf


def _coseno(a: dict[int, float], b: dict[int, float]) -> float:
    if len(a) > len(b):
        a, b = b, a
    return sum(v * b.get(idx, 0.0) for idx, v in a.items())


# ------------------------------------------------------------------- motor


def recomendar(
    conn: sqlite3.Connection,
    limite: int | None = None,
    min_muestras: int = MIN_MUESTRAS,
) -> list[dict]:
    """Puntúa los pendientes y devuelve la lista ordenada por encaje.

    Solo devuelve títulos con al menos un motivo: lo que no se puede
    justificar no se recomienda. Cada elemento:
    {tt, titulo, year, imdb, score, encaje, razones: [...]}.
    """
    valoradas, pendientes, meta = _datos(conn)
    if not valoradas or not pendientes:
        return []

    facetas = _facetas_por_tt(conn)
    global_media = _media(valoradas.values())
    acum: dict[str, dict[str, dict]] = {}
    for tt, nota in valoradas.items():
        for faceta, valores in facetas.get(tt, {}).items():
            for valor in valores:
                slot = acum.setdefault(faceta, {}).setdefault(
                    valor, {"n": 0, "notas": [], "diff": []})
                slot["n"] += 1
                slot["notas"].append(nota)
                imdb = meta.get(tt, {}).get("imdb")
                if imdb is not None:
                    slot["diff"].append(nota - imdb)

    perfil_facetas: dict[str, dict[str, dict]] = {}
    for faceta, valores in acum.items():
        perfil_facetas[faceta] = {}
        for valor, slot in valores.items():
            if slot["n"] < min_muestras:
                continue
            media = _media(slot["notas"])
            perfil_facetas[faceta][valor] = {
                "n": slot["n"],
                "media": media,
                "lift": media - global_media,
                "diff_imdb": _media(slot["diff"]),
            }

    saga = _colecciones(conn)
    vectores, _idf = indice_sinopsis(conn)
    favoritos = [tt for tt, nota in valoradas.items() if nota >= 8]

    resultados = []
    for tt in pendientes:
        puntos: list[tuple[float, str, str, str]] = []  # peso, capa, clave, texto

        for faceta, valores in facetas.get(tt, {}).items():
            peso_faceta = PESOS.get(faceta, 0.5)
            for valor in valores:
                dato = perfil_facetas.get(faceta, {}).get(valor)
                if not dato:
                    continue
                etiqueta = ETIQUETAS.get(faceta, faceta)
                articulo = ARTICULO.get(faceta, "el")
                lift = dato["lift"]
                if abs(lift) >= UMBRAL_LIFT:
                    if lift > 0:
                        texto = (f"{articulo.capitalize()} {etiqueta} {valor} te sale alto: "
                                 f"{dato['media']:.1f} frente a tu {global_media:.1f} global")
                    else:
                        texto = (f"{articulo.capitalize()} {etiqueta} {valor} se te da flojo: "
                                 f"{dato['media']:.1f} frente a tu {global_media:.1f} global")
                    puntos.append((lift * peso_faceta, "afinidad",
                                   f"{faceta}:{valor}", texto))
                if dato["diff_imdb"] <= UMBRAL_ANTIPROFIL:
                    puntos.append((
                        dato["diff_imdb"] * peso_faceta * 0.5,
                        "antiperfil",
                        f"anti:{faceta}:{valor}",
                        f"{PREPOSICION.get(faceta, 'En')} {articulo} {etiqueta} {valor}, "
                        f"IMDb suele ganarte ({dato['diff_imdb']:+.1f} de media)"))

        for otro, nombre in saga.get(tt, []):
            if otro in valoradas:
                puntos.append((
                    1.5,
                    "saga",
                    f"saga:{otro}",
                    f"Comparte saga con {meta[otro]['titulo']}, que valoraste "
                    f"{valoradas[otro]}"))

        vector = vectores.get(tt)
        if vector:
            mejor = []
            for otro in favoritos:
                otro_vec = vectores.get(otro)
                if not otro_vec:
                    continue
                if len(set(vector) & set(otro_vec)) < MIN_TERMINOS_COMUNES:
                    continue
                sim = _coseno(vector, otro_vec)
                if sim >= UMBRAL_SIMILITUD:
                    mejor.append((sim, otro))
            mejor.sort(key=lambda par: (-par[0], par[1]))
            for sim, otro in mejor[:2]:
                puntos.append((
                    sim * 2.0,
                    "similitud",
                    f"sim:{otro}",
                    f"Se parece a {meta[otro]['titulo']}, que valoraste {valoradas[otro]}"))

        imdb = meta.get(tt, {}).get("imdb")
        score = sum(p for p, _, _, _ in puntos)
        if imdb is not None:
            score += PESO_IMDB * imdb

        razones = _elegir_motivos(puntos)
        resultados.append({
            "tt": tt,
            "titulo": meta[tt]["titulo"],
            "year": meta[tt]["year"],
            "imdb": imdb,
            "score": round(score, 3),
            "razones": razones,
        })

    resultados.sort(key=lambda r: (-r["score"], r["tt"]))
    # Solo entra lo que se puede justificar: una recomendación sin motivo no
    # sirve para decidir, y el título sin explicación solo añade ruido.
    resultados = [r for r in resultados if r["razones"]]
    if limite is not None:
        resultados = resultados[:limite]

    if resultados:
        mejor_score = max(r["score"] for r in resultados)
        for r in resultados:
            encaje = 0 if mejor_score <= 0 else round(100 * r["score"] / mejor_score)
            r["encaje"] = max(0, min(100, encaje))
    return resultados


def _elegir_motivos(puntos, maximo: int = 3) -> list[str]:
    """Elige hasta `maximo` motivos, prefers uno de cada capa.

    Tres razones de la misma faceta ("el género X", "el director Y", "el
    actor Z") dicen menos que tres razones de capas distintas ("tu género te
    sale alto", "IMDb te gana ahí", "comparte saga con..."). Así que primero
    se toma el mejor motivo de cada capa y después se rellena con los
    siguientes mejores, sin repetir la misma faceta.
    """
    if not puntos:
        return []
    orden = sorted(puntos, key=lambda p: (-p[0], p[3]))
    elegidos: list[tuple[float, str, str, str]] = []
    claves: set[str] = set()

    for capa in ("saga", "similitud", "antiperfil", "afinidad"):
        for punto in orden:
            if punto[1] == capa and punto[2] not in claves:
                elegidos.append(punto)
                claves.add(punto[2])
                break
        if len(elegidos) >= maximo:
            break

    elegidos.sort(key=lambda p: (-p[0], p[3]))
    for punto in orden:
        if len(elegidos) >= maximo:
            break
        if punto[2] in claves:
            continue
        elegidos.append(punto)
        claves.add(punto[2])

    return [p[3] for p in elegidos[:maximo]]


def resumen_perfil(conn: sqlite3.Connection, maximo: int = 5,
                    min_muestras: int = MIN_MUESTRAS) -> dict:
    """Tu gusto, medido: qué facetas te salen por encima o por debajo de tu media.

    El orden no es el lift crudo sino un lift "encogido" por la evidencia
    (lift * n / (n + PESO_EVIDENCIA)): un director con dos títulos y un
    +1.9 no puede pesar más que un género con diecisiete y un +0.9.
    """
    p = perfil(conn, min_muestras=min_muestras)
    if not p["n_valoradas"]:
        return {"media_global": 0.0, "n_valoradas": 0, "alto": [], "bajo": []}

    items = []
    for faceta in ("genero", "director", "actor"):
        for valor, d in p["facetas"].get(faceta, {}).items():
            if abs(d["lift"]) < UMBRAL_LIFT:
                continue
            items.append({
                "faceta": ETIQUETAS.get(faceta, faceta),
                "valor": valor,
                "media": d["media"],
                "lift": d["lift"],
                "n": d["n"],
                "peso": d["lift"] * d["n"] / (d["n"] + PESO_EVIDENCIA),
            })

    alto = sorted(items, key=lambda i: (-i["peso"], i["valor"]))[:maximo]
    bajo = sorted(items, key=lambda i: (i["peso"], i["valor"]))[:maximo]
    return {"media_global": p["global"], "n_valoradas": p["n_valoradas"],
            "alto": alto, "bajo": bajo}


def recomendar_desde_db(db_path: str | Path, limite: int | None = None) -> list[dict]:
    """Atajo: abre la base y devuelve las recomendaciones."""
    conn = get_connection(db_path)
    try:
        return recomendar(conn, limite=limite)
    finally:
        conn.close()
