class Equipo:
    def __init__(self, id, nombre, logo, posicion, puntos, forma,
                 PT, VT, ET, DT, PC, VC, EC, DC, PF, VF, EF, DF,
                 temporada, goles_favor, goles_contra,
                 goles_favor_casa, goles_contra_casa,
                 goles_favor_fuera, goles_contra_fuera,
                 id_liga, nombre_liga, pais, bandera, logo_liga):

        # ------ Datos básicos ------
        self.id = id or 0
        self.nombre = nombre or ""
        self.logo = logo or ""
        self.posicion = posicion or 0
        self.puntos = puntos or 0

        # ------ Forma ------
        # A veces viene None → convertir a string vacío
        forma = forma or ""
        victorias_5 = forma.count("W")
        empates_5 = forma.count("D")

        # Dividir entre 15 pero evitar división entre cero
        self.forma = (victorias_5*3 + empates_5*1) / (len(forma)*3) \
            if len(forma) > 0 else 0

        # ------ Partidos ------
        self.PT = PT or 0
        self.VT = VT or 0
        self.ET = ET or 0
        self.DT = DT or 0

        self.PC = PC or 0
        self.VC = VC or 0
        self.EC = EC or 0
        self.DC = DC or 0

        self.PF = PF or 0
        self.VF = VF or 0
        self.EF = EF or 0
        self.DF = DF or 0

        # ------ Goles totales ------
        self.goles_favor = goles_favor or 0
        self.goles_contra = goles_contra or 0

        if self.PT > 0:
            self.goles_favor_por_partido = \
                self.goles_favor / self.PT
            self.goles_contra_por_partido = \
                self.goles_contra / self.PT
        else:
            self.goles_favor_por_partido = 0
            self.goles_contra_por_partido = 0

        self.dif_goles = self.goles_favor - self.goles_contra

        # ------ Goles en casa ------
        self.goles_favor_casa = goles_favor_casa or 0
        self.goles_contra_casa = goles_contra_casa or 0

        if self.PC > 0:
            self.goles_favor_casa_por_partido = \
                self.goles_favor_casa / self.PC
            self.goles_contra_casa_por_partido = \
                self.goles_contra_casa / self.PC
        else:
            self.goles_favor_casa_por_partido = 0
            self.goles_contra_casa_por_partido = 0

        self.dif_goles_casa = self.goles_favor_casa - self.goles_contra_casa

        # ------ Goles fuera ------
        self.goles_favor_fuera = goles_favor_fuera or 0
        self.goles_contra_fuera = goles_contra_fuera or 0

        if self.PF > 0:
            self.goles_favor_fuera_por_partido = \
                self.goles_favor_fuera / self.PF
            self.goles_contra_fuera_por_partido = \
                self.goles_contra_fuera / self.PF
        else:
            self.goles_favor_fuera_por_partido = 0
            self.goles_contra_fuera_por_partido = 0

        self.dif_goles_fuera = self.goles_favor_fuera - self.goles_contra_fuera

        # ------ Últimos partidos ------
        self.ultimos_5 = forma

        # ------ Liga ------
        self.id_liga = id_liga or 0
        self.nombre_liga = nombre_liga or ""
        self.pais = pais or ""
        self.bandera = bandera or ""
        self.logo_liga = logo_liga or ""

        # Para referencia futura
        self.temporada = temporada or ""

    def to_dict(self):
        return {
            "id": self.id,
            "nombre": self.nombre,
            "logo": self.logo,
            "posicion": self.posicion,
            "puntos": self.puntos,
            "forma": self.forma,
            "PT": self.PT,
            "VT": self.VT,
            "ET": self.ET,
            "DT": self.DT,
            "PC": self.PC,
            "VC": self.VC,
            "EC": self.EC,
            "DC": self.DC,
            "PF": self.PF,
            "VF": self.VF,
            "EF": self.EF,
            "DF": self.DF,
            "temporada": self.temporada,
            "goles_favor": self.goles_favor,
            "goles_favor_por_partido":
                self.goles_favor_por_partido,
            "goles_contra": self.goles_contra,
            "goles_contra_por_partido":
                self.goles_contra_por_partido,
            "diferencia_goles": self.dif_goles,
            "goles_favor_casa": self.goles_favor_casa,
            "goles_favor_casa_por_partido":
                self.goles_favor_casa_por_partido,
            "goles_contra_casa": self.goles_contra_casa,
            "goles_contra_casa_por_partido":
                self.goles_contra_casa_por_partido,
            "diferencia_goles_casa": self.dif_goles_casa,
            "goles_favor_fuera": self.goles_favor_fuera,
            "goles_favor_fuera_por_partido":
                self.goles_favor_fuera_por_partido,
            "goles_contra_fuera": self.goles_contra_fuera,
            "goles_contra_fuera_por_partido":
                self.goles_contra_fuera_por_partido,
            "diferencia_goles_fuera": self.dif_goles_fuera,
            "ultimos_partidos": self.ultimos_5,
            "liga": {
                "id": self.id_liga,
                "nombre": self.nombre_liga,
                "pais": self.pais,
                "bandera": self.bandera,
                "logo": self.logo_liga
            }
        }
