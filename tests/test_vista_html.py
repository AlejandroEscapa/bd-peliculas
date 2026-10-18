"""Panel HTML: contiene la lista completa y las secciones KPI."""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.generar_vista import generar
from src.sync import import_csv

FIXTURE = ROOT / "tests" / "fixtures" / "mini.csv"


class TestVistaHtml(unittest.TestCase):
    def test_lista_completa_con_todos_los_titulos(self):
        tmp = tempfile.TemporaryDirectory()
        db_path = Path(tmp.name) / "test.db"
        import_csv(FIXTURE, db_path)
        pagina = generar(db_path)
        # Los 3 títulos del fixture aparecen en la lista completa.
        for titulo in ("Cadena perpetua", "El padrino", "Hunter"):
            self.assertIn(titulo, pagina)
        # Sin nota se marca NP (no 'pendiente').
        self.assertIn('>NP<', pagina)
        self.assertNotIn('>pendiente<', pagina)
        # Géneros limitados a 3 en muestra (Hunter trae 5: 3 + '...').
        self.assertIn('...', pagina)
        # Secciones KPI presentes.
        for seccion in ("Tus favoritas", "En seguimiento", "Lista completa"):
            self.assertIn(seccion, pagina)
        tmp.cleanup()


if __name__ == "__main__":
    unittest.main()
