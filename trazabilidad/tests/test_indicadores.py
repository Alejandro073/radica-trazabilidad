from datetime import date

from trazabilidad import indicadores
from trazabilidad.models import CausalGlosa, Estado, Glosa, Resultado

from .base import BaseTest


class IndicadoresTest(BaseTest):
    def test_porcentajes_de_glosa(self):
        for i in range(4):
            c = self.crear_cuenta(valor=1_000_000)
            c.estado = Estado.RESULTADO
            c.resultado = Resultado.GLOSADA if i == 0 else Resultado.ACEPTADA
            c.save()
            if i == 0:
                Glosa.objects.create(cuenta=c, causal=CausalGlosa.SOPORTES, valor_glosado=400_000)
        r = indicadores.resumen_glosas()
        self.assertEqual(r["radicadas"], 4)
        self.assertEqual(r["glosadas"], 1)
        self.assertEqual(r["pct_cuentas"], 25.0)
        self.assertEqual(r["valor_radicado"], 4_000_000)
        self.assertEqual(r["pct_valor"], 10.0)
        self.assertEqual(indicadores.causas_de_glosa()[0]["causal"], "Soportes")
        self.assertEqual(indicadores.por_entidad()[0]["entidad"], "EPS Prueba")

    def test_tiempo_promedio_y_plazo(self):
        for dias in (4, 8):
            c = self.crear_cuenta()
            c.atencion.fecha_egreso = date(2026, 10, 5)
            c.atencion.save()
            c.estado = Estado.RADICADA
            c.fecha_radicacion = date(2026, 10, 5 + dias)
            c.save()
        t = indicadores.tiempo_promedio_radicacion()
        self.assertEqual(t["n"], 2)
        self.assertEqual(t["promedio_dias"], 6.0)
        self.assertEqual(t["pct_en_plazo"], 100.0)

    def test_sin_datos_no_falla(self):
        d = indicadores.todos()
        self.assertEqual(d["glosas"]["pct_cuentas"], 0.0)
        self.assertEqual(d["tiempos"]["promedio_dias"], 0.0)
