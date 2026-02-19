"""
Feature Engineering v2 para RDScore.

Mejoras sobre v1:
- Features históricos (racha, H2H, días de descanso)
- Features contextuales (win rate casa/fuera, BTTS/Over rate)
- Calculados desde partidos.pkl, sin API calls extra

Total: 52 features (vs 30 en v1)
"""

from datetime import datetime
from collections import defaultdict
import numpy as np


def _safe(x):
    """Convierte a float seguro."""
    try:
        if x is None:
            return 0.0
        return float(x)
    except Exception:
        return 0.0


def _parse_fecha(fecha_str):
    """Convierte 'dd/mm/YYYY' a datetime.date."""
    try:
        return datetime.strptime(fecha_str, "%d/%m/%Y").date()
    except (ValueError, TypeError):
        return None


class FeatureExtractor:
    """
    Extrae features mejorados para predicción de partidos.

    Necesita la lista completa de partidos para calcular features
    históricos (H2H, racha, días de descanso), evitando data leakage
    filtrando siempre por fecha < fecha_partido.
    """

    def __init__(self, todos_los_partidos):
        """
        Pre-procesa el historial de partidos para acceso rápido.

        Args:
            todos_los_partidos: Lista de objetos Partido (de partidos.pkl)
        """
        self.partidos_ft = [p for p in todos_los_partidos if p.estado == "FT"]
        self._build_indices()

    def _build_indices(self):
        """Construye índices para búsqueda rápida por equipo y H2H."""
        self.por_equipo = defaultdict(list)
        self.h2h_index = defaultdict(list)

        for p in self.partidos_ft:
            fecha = _parse_fecha(p.fecha)
            if fecha is None:
                continue

            id_l = p.equipo_local.id
            id_v = p.equipo_visitante.id

            self.por_equipo[id_l].append((fecha, p, 'home'))
            self.por_equipo[id_v].append((fecha, p, 'away'))

            # H2H bidireccional: clave siempre ordenada
            key = (min(id_l, id_v), max(id_l, id_v))
            self.h2h_index[key].append((fecha, p))

        # Ordenar por fecha para iterar eficientemente
        for k in self.por_equipo:
            self.por_equipo[k].sort(key=lambda x: x[0])
        for k in self.h2h_index:
            self.h2h_index[k].sort(key=lambda x: x[0])

    # =================================================================
    # FUNCIONES DE CONSULTA HISTÓRICA
    # =================================================================

    def _get_racha(self, equipo_id, antes_de, n=5, ubicacion=None):
        """
        Racha de los últimos N partidos del equipo antes de una fecha.

        Args:
            equipo_id: ID del equipo
            antes_de: datetime.date — solo partidos anteriores
            n: Número de partidos
            ubicacion: 'home'/'away'/None (todos)

        Returns:
            dict con puntos(norm), gf_avg, gc_avg, n_real
        """
        entradas = self.por_equipo.get(equipo_id, [])
        recientes = []

        for fecha, p, ub in reversed(entradas):
            if fecha >= antes_de:
                continue
            if ubicacion and ub != ubicacion:
                continue
            recientes.append((p, ub))
            if len(recientes) >= n:
                break

        if not recientes:
            return {'pts': 0.0, 'gf': 0.0, 'gc': 0.0, 'n': 0}

        pts = gf = gc = 0
        for p, ub in recientes:
            if ub == 'home':
                gf += max(0, p.goles_local)
                gc += max(0, p.goles_visitante)
                if p.resultado == 1:
                    pts += 3
                elif p.resultado == 0:
                    pts += 1
            else:
                gf += max(0, p.goles_visitante)
                gc += max(0, p.goles_local)
                if p.resultado == 2:
                    pts += 3
                elif p.resultado == 0:
                    pts += 1

        nr = len(recientes)
        return {
            'pts': pts / (nr * 3),  # Normalizado 0-1
            'gf': gf / nr,
            'gc': gc / nr,
            'n': nr
        }

    def _get_h2h(self, id_local, id_visitante, antes_de, n=10):
        """
        Historial H2H entre dos equipos.

        Returns:
            dict con wins_l, wins_v, draws (normalizados), diff_gf, n_real
        """
        key = (min(id_local, id_visitante), max(id_local, id_visitante))
        entradas = self.h2h_index.get(key, [])

        recientes = []
        for fecha, p in reversed(entradas):
            if fecha >= antes_de:
                continue
            recientes.append(p)
            if len(recientes) >= n:
                break

        if not recientes:
            return {'wl': 0, 'wv': 0, 'dr': 0, 'dgf': 0, 'n': 0}

        wl = wv = dr = gfl = gfv = 0
        for p in recientes:
            gl = max(0, p.goles_local)
            gv = max(0, p.goles_visitante)
            if p.equipo_local.id == id_local:
                gfl += gl
                gfv += gv
                if p.resultado == 1:
                    wl += 1
                elif p.resultado == 2:
                    wv += 1
                else:
                    dr += 1
            else:
                gfl += gv
                gfv += gl
                if p.resultado == 2:
                    wl += 1
                elif p.resultado == 1:
                    wv += 1
                else:
                    dr += 1

        nr = len(recientes)
        return {
            'wl': wl / nr, 'wv': wv / nr, 'dr': dr / nr,
            'dgf': (gfl - gfv) / nr, 'n': nr
        }

    def _get_dias_descanso(self, equipo_id, fecha_partido):
        """Días desde el último partido del equipo."""
        entradas = self.por_equipo.get(equipo_id, [])
        for fecha, _, _ in reversed(entradas):
            if fecha < fecha_partido:
                return (fecha_partido - fecha).days
        return 14  # Default si no hay historial

    def _get_btts_over_rate(self, equipo_id, antes_de, n=10):
        """% de partidos con BTTS y Over 2.5 del equipo (últimos N)."""
        entradas = self.por_equipo.get(equipo_id, [])
        recientes = []
        for fecha, p, _ in reversed(entradas):
            if fecha >= antes_de:
                continue
            recientes.append(p)
            if len(recientes) >= n:
                break

        if not recientes:
            return {'btts': 0.5, 'over': 0.5}

        nr = len(recientes)
        btts = sum(1 for p in recientes if p.ambos_marcan == 1)
        over = sum(1 for p in recientes if p.mas_2_5 == 1)
        return {'btts': btts / nr, 'over': over / nr}

    def _get_stats_acumuladas(self, equipo_id, antes_de, liga_id, temporada,
                               ubicacion=None):
        """
        Calcula estadísticas acumuladas del equipo en la liga/temporada actual
        hasta una fecha determinada (sin incluirla).

        Args:
            ubicacion: 'home'/'away'/None (todos)
        """
        entradas = self.por_equipo.get(equipo_id, [])
        pts = gf = gc = wins = n = 0

        for fecha, p, ub in entradas:
            if fecha >= antes_de:
                continue
            if p.id_liga != liga_id or p.temporada != temporada:
                continue
            if ubicacion and ub != ubicacion:
                continue

            n += 1
            if ub == 'home':
                gf += max(0, p.goles_local)
                gc += max(0, p.goles_visitante)
                if p.resultado == 1:
                    pts += 3
                    wins += 1
                elif p.resultado == 0:
                    pts += 1
            else:
                gf += max(0, p.goles_visitante)
                gc += max(0, p.goles_local)
                if p.resultado == 2:
                    pts += 3
                    wins += 1
                elif p.resultado == 0:
                    pts += 1

        if n == 0:
            return {'ppm': 1.0, 'gf': 1.0, 'gc': 1.0, 'wr': 0.33, 'n': 0}

        return {
            'ppm': pts / n,
            'gf': gf / n,
            'gc': gc / n,
            'wr': wins / n,
            'n': n
        }

    # =================================================================
    # EXTRACCIÓN DE FEATURES
    # =================================================================


    def extraer(self, partido):
        """
        Extrae 50 features para un partido (históricos + acumulados, sin leakage).

        Returns:
            np.array shape (1, 50)
        """
        el = partido.equipo_local
        ev = partido.equipo_visitante
        fecha = _parse_fecha(partido.fecha)
        lid = partido.id_liga
        temp = partido.temporada

        # --- BLOQUE A: Acumulados Temporada (20) ---
        if fecha:
            # General
            acc_l = self._get_stats_acumuladas(el.id, fecha, lid, temp)
            acc_v = self._get_stats_acumuladas(ev.id, fecha, lid, temp)
            # Casa/Fuera específico
            acc_lc = self._get_stats_acumuladas(el.id, fecha, lid, temp, 'home')
            acc_vf = self._get_stats_acumuladas(ev.id, fecha, lid, temp, 'away')
        else:
            acc_l = acc_v = acc_lc = acc_vf = {
                'ppm': 1.0, 'gf': 1.0, 'gc': 1.0, 'wr': 0.33, 'n': 0
            }

        acumulados = [
            # Stats generales (8)
            acc_l['ppm'], acc_l['gf'], acc_l['gc'], acc_l['wr'],
            acc_v['ppm'], acc_v['gf'], acc_v['gc'], acc_v['wr'],
            # Casa/fuera específico (4)
            acc_lc['gf'], acc_lc['gc'],
            acc_vf['gf'], acc_vf['gc'],
            # Diferencias (4)
            acc_l['ppm'] - acc_v['ppm'],
            acc_l['gf'] - acc_v['gc'],      # ataque local vs defensa visitante
            acc_v['gf'] - acc_l['gc'],       # ataque visitante vs defensa local
            acc_lc['gf'] - acc_vf['gc'],     # ataque casa vs defensa fuera
            # Ratios (2)
            acc_l['gf'] / (acc_v['gc'] + 0.1),
            acc_v['gf'] / (acc_l['gc'] + 0.1),
            # Profundidad (2) — cuántos partidos llevamos en la temporada
            min(acc_l['n'], 38) / 38,
            min(acc_v['n'], 38) / 38,
        ]

        # --- BLOQUE B: Features históricos (26) ---
        if fecha:
            rl = self._get_racha(el.id, fecha, n=5)
            rv = self._get_racha(ev.id, fecha, n=5)
            rl_c = self._get_racha(el.id, fecha, n=5, ubicacion='home')
            rv_f = self._get_racha(ev.id, fecha, n=5, ubicacion='away')
            h2h = self._get_h2h(el.id, ev.id, fecha)
            dl = self._get_dias_descanso(el.id, fecha)
            dv = self._get_dias_descanso(ev.id, fecha)
            br_l = self._get_btts_over_rate(el.id, fecha)
            br_v = self._get_btts_over_rate(ev.id, fecha)
        else:
            rl = rv = rl_c = rv_f = {'pts': 0, 'gf': 0, 'gc': 0, 'n': 0}
            h2h = {'wl': 0, 'wv': 0, 'dr': 0, 'dgf': 0, 'n': 0}
            dl = dv = 14
            br_l = br_v = {'btts': 0.5, 'over': 0.5}

        historicos = [
            # Racha general (6)
            rl['pts'], rl['gf'], rl['gc'],
            rv['pts'], rv['gf'], rv['gc'],
            # Racha casa/fuera (4)
            rl_c['pts'], rl_c['gf'],
            rv_f['pts'], rv_f['gf'],
            # Diferencia rachas (2)
            rl['pts'] - rv['pts'],
            rl['gf'] - rv['gf'],
            # H2H (5)
            h2h['wl'], h2h['wv'], h2h['dr'],
            h2h['dgf'],
            min(h2h['n'], 10) / 10,
            # Descanso (3)
            min(dl, 30) / 30,
            min(dv, 30) / 30,
            (dl - dv) / 30,
            # BTTS/Over rates (6)
            br_l['btts'], br_v['btts'],
            br_l['over'], br_v['over'],
            (br_l['btts'] + br_v['btts']) / 2,
            (br_l['over'] + br_v['over']) / 2,
        ]

        # --- BLOQUE C: Buckets (4) ---
        buckets = [
            1 if acc_l['ppm'] >= 1.8 else 0,    # ¿Equipo local fuerte?
            1 if acc_v['ppm'] >= 1.8 else 0,    # ¿Equipo visitante fuerte?
            1 if acc_l['ppm'] >= 2.2 else 0,    # ¿Equipo local top?
            1 if acc_v['ppm'] >= 2.2 else 0,    # ¿Equipo visitante top?
        ]

        # --- VECTOR FINAL: 20+26+4 = 50 features ---
        X = acumulados + historicos + buckets
        return np.array(X).reshape(1, -1)

    @property
    def n_features(self):
        return 50

    FEATURE_NAMES = [
        # Acumulados generales (8)
        'acc_l_ppm', 'acc_l_gf', 'acc_l_gc', 'acc_l_wr',
        'acc_v_ppm', 'acc_v_gf', 'acc_v_gc', 'acc_v_wr',
        # Casa/fuera específico (4)
        'acc_lc_gf', 'acc_lc_gc', 'acc_vf_gf', 'acc_vf_gc',
        # Diferencias (4)
        'd_ppm', 'd_atk_l_def_v', 'd_atk_v_def_l', 'd_atk_casa_def_fuera',
        # Ratios (2)
        'r_atk_l_def_v', 'r_atk_v_def_l',
        # Profundidad (2)
        'depth_l', 'depth_v',
        # Racha general (6)
        'rch_l_pts', 'rch_l_gf', 'rch_l_gc',
        'rch_v_pts', 'rch_v_gf', 'rch_v_gc',
        # Racha casa/fuera (4)
        'rch_lc_pts', 'rch_lc_gf', 'rch_vf_pts', 'rch_vf_gf',
        # Diff rachas (2)
        'd_rch_pts', 'd_rch_gf',
        # H2H (5)
        'h2h_wl', 'h2h_wv', 'h2h_dr', 'h2h_dgf', 'h2h_depth',
        # Descanso (3)
        'desc_l', 'desc_v', 'd_desc',
        # BTTS/Over rates (6)
        'btts_l', 'btts_v', 'over_l', 'over_v', 'avg_btts', 'avg_over',
        # Buckets (4)
        'bkt_l_strong', 'bkt_v_strong', 'bkt_l_top', 'bkt_v_top',
    ]

