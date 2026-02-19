class Partido:
    def __init__(self, id_partido, estado, id_liga, temporada, jornada,
                 equipo_local, equipo_visitante,
                 fecha, hora, ciudad, estadio, arbitro,
                 cuota_local, cuota_empate, cuota_visitante,
                 cuota_over, cuota_under, cuota_btts, cuota_btts_no,
                 goles_local, goles_visitante):

        # Identificadores
        self.id_partido = id_partido or -1
        self.estado = estado or "Estado desconocido"
        self.id_liga = id_liga or -1
        self.temporada = temporada or -1
        self.jornada = jornada or "Jornada desconocida"

        # Equipos (ya comprobados en buscar_equipo)
        self.equipo_local = equipo_local
        self.equipo_visitante = equipo_visitante

        # Datos del partido
        self.fecha = fecha or "01/01/1970"
        self.hora = hora or "00:00"
        self.ciudad = ciudad or "Ciudad desconocida"
        self.estadio = estadio or "Estadio desconocido"
        self.arbitro = arbitro or "Árbitro no disponible"

        # Cuotas seguras
        self.cuota_local = \
            cuota_local if cuota_local not in (None, "") else -1
        self.cuota_empate = \
            cuota_empate if cuota_empate not in (None, "") else -1
        self.cuota_visitante = \
            cuota_visitante if cuota_visitante not in (None, "") else -1
        self.cuota_over = \
            cuota_over if cuota_over not in (None, "") else -1
        self.cuota_under = \
            cuota_under if cuota_under not in (None, "") else -1
        self.cuota_btts = \
            cuota_btts if cuota_btts not in (None, "") else -1
        self.cuota_btts_no = \
            cuota_btts_no if cuota_btts_no not in (None, "") else -1

        # Marcadores seguros
        self.goles_local = \
            goles_local if goles_local is not None else -1
        self.goles_visitante = \
            goles_visitante if goles_visitante is not None else -1

        # Resultado seguro
        if self.goles_local == -1 or self.goles_visitante == -1:
            self.resultado = -1
        else:
            if self.goles_local > self.goles_visitante:
                self.resultado = 1
            elif self.goles_local < self.goles_visitante:
                self.resultado = 2
            else:
                self.resultado = 0

        # Variables calculadas
        self.ambos_marcan = \
            int(self.goles_local > 0 and self.goles_visitante > 0)
        self.local_marca = \
            int(self.goles_local > 0)
        self.visitante_marca = \
            int(self.goles_visitante > 0)
        self.mas_2_5 = int(
            self.goles_local != -1 and
            self.goles_visitante != -1 and
            (self.goles_local + self.goles_visitante) > 2
        )

        # Iniciar predicción vacía
        self.prediccion = "No hay predicción disponible"

    def to_dict(self):
        return {
            'id_partido': self.id_partido,
            'estado': self.estado,
            'id_liga': self.id_liga,
            'temporada': self.temporada,
            'jornada': self.jornada,
            'equipo_local': self.equipo_local.nombre,
            'equipo_visitante': self.equipo_visitante.nombre,
            'estadisticas_local': self.equipo_local.to_dict(),
            'estadisticas_visitante': self.equipo_visitante.to_dict(),
            'fecha': self.fecha,
            'hora': self.hora,
            'ciudad': self.ciudad,
            'estadio': self.estadio,
            'arbitro': self.arbitro,
            'cuota_local': self.cuota_local,
            'cuota_empate': self.cuota_empate,
            'cuota_visitante': self.cuota_visitante,
            'cuota_over': self.cuota_over,
            'cuota_under': self.cuota_under,
            'cuota_btts': self.cuota_btts,
            'cuota_btts_no': self.cuota_btts_no,
            'goles_local': self.goles_local,
            'goles_visitante': self.goles_visitante,
            'resultado': self.resultado,
            'ambos_marcan': self.ambos_marcan,
            'local_marca': self.local_marca,
            'visitante_marca': self.visitante_marca,
            'mas_2_5': self.mas_2_5,
            'prediccion': self.prediccion
        }
