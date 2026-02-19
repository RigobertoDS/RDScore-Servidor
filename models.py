from extensions import db, bcrypt
from datetime import datetime, timezone

class Usuario(db.Model):
    __tablename__ = "usuarios"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def set_password(self, password):
        self.password_hash = bcrypt.generate_password_hash(password).decode('utf-8')

    def check_password(self, password):
        if self.password_hash:
            return bcrypt.check_password_hash(self.password_hash, password)
        return False

    def to_dict(self):
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "created_at": self.created_at.isoformat()
        }

class TokenBlocklist(db.Model):
    __tablename__ = "token_blocklist"
    id = db.Column(db.Integer, primary_key=True)
    jti = db.Column(db.String(36), nullable=False, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "token_id": self.id,
            "jti": self.jti,
            "created_at": self.created_at
        }

# --- Nuevas Tablas para Datos Deportivos ---

class Liga(db.Model):
    __tablename__ = "ligas"
    id = db.Column(db.Integer, primary_key=True)  # ID de la API externa
    nombre = db.Column(db.String(100), nullable=False)
    pais = db.Column(db.String(100))
    logo = db.Column(db.String(255))
    bandera = db.Column(db.String(255))
    
    # Relaciones
    equipos = db.relationship('Equipo', backref='liga', lazy=True)
    partidos = db.relationship('Partido', backref='liga', lazy=True)

    def to_dict(self):
        return {
            "id": self.id,
            "nombre": self.nombre,
            "pais": self.pais,
            "logo": self.logo,
            "bandera": self.bandera
        }

class Equipo(db.Model):
    __tablename__ = "equipos"
    id = db.Column(db.Integer, primary_key=True) # ID de la API
    id_liga = db.Column(db.Integer, db.ForeignKey('ligas.id'), primary_key=True) # Clave compuesta
    nombre = db.Column(db.String(100), nullable=False)
    logo = db.Column(db.String(255))
    
    # Estadísticas de la competición específica
    posicion = db.Column(db.Integer)
    puntos = db.Column(db.Integer)
    forma = db.Column(db.String(50))
    temporada = db.Column(db.Integer) # Informativo
    
    # Stats detallados (PT, VT, goles, etc.)
    stats_json = db.Column(db.JSON) 
    
    def to_dict(self):
        s = self.stats_json or {}
        # Safely get values, defaulting to 0
        def get_stat(key):
            val = s.get(key, 0)
            return val if val is not None else 0

        pt = get_stat("PT")
        pc = get_stat("PC")
        pf = get_stat("PF")
        
        gf = get_stat("goles_favor")
        gc = get_stat("goles_contra")
        gfc = get_stat("goles_favor_casa")
        gcc = get_stat("goles_contra_casa")
        gff = get_stat("goles_favor_fuera")
        gcf = get_stat("goles_contra_fuera")

        base = {
            "id": self.id,
            "id_liga": self.id_liga,
            "nombre": self.nombre,
            "logo": self.logo,
            "liga": self.liga.to_dict() if self.liga else None,
            "posicion": self.posicion,
            "puntos": self.puntos,
            "forma": self.forma,
            "temporada": self.temporada,
            
            # Derived Stats (Required by Android)
            "goles_favor_por_partido": round(gf / pt, 2) if pt > 0 else 0,
            "goles_contra_por_partido": round(gc / pt, 2) if pt > 0 else 0,
            "diferencia_goles": gf - gc,
            
            "goles_favor_casa_por_partido": round(gfc / pc, 2) if pc > 0 else 0,
            "goles_contra_casa_por_partido": round(gcc / pc, 2) if pc > 0 else 0,
            "diferencia_goles_casa": gfc - gcc,
            
            "goles_favor_fuera_por_partido": round(gff / pf, 2) if pf > 0 else 0,
            "goles_contra_fuera_por_partido": round(gcf / pf, 2) if pf > 0 else 0,
            "diferencia_goles_fuera": gff - gcf,
            
            "ultimos_partidos": s.get("ultimos_5", "")
        }
        if self.stats_json:
            base.update(self.stats_json)
        return base

class Partido(db.Model):
    __tablename__ = "partidos"
    id = db.Column(db.Integer, primary_key=True) # ID API externa
    fecha = db.Column(db.Date, index=True, nullable=False)
    hora = db.Column(db.String(10))
    estado = db.Column(db.String(10), index=True) # FT, NS, PST
    id_liga = db.Column(db.Integer, db.ForeignKey('ligas.id'), nullable=False)
    temporada = db.Column(db.Integer)
    jornada = db.Column(db.String(50))
    
    # Equipos (Claves foráneas compuestas)
    id_local = db.Column(db.Integer, nullable=False)
    id_visitante = db.Column(db.Integer, nullable=False)
    
    # Definir relaciones manualmente para Composite Foreign Keys
    __table_args__ = (
        db.ForeignKeyConstraint(
            ['id_local', 'id_liga'],
            ['equipos.id', 'equipos.id_liga'],
        ),
        db.ForeignKeyConstraint(
            ['id_visitante', 'id_liga'],
            ['equipos.id', 'equipos.id_liga'],
        ),
    )
    
    # Resultado
    goles_local = db.Column(db.Integer)
    goles_visitante = db.Column(db.Integer)
    resultado = db.Column(db.Integer) # 1, X(0), 2
    
    # Datos explícitos (antes en info_extra/calculados)
    ambos_marcan = db.Column(db.Integer)   # 0 o 1
    local_marca = db.Column(db.Integer)    # 0 o 1
    visitante_marca = db.Column(db.Integer) # 0 o 1
    mas_2_5 = db.Column(db.Integer)        # 0 o 1
    
    # Datos JSON flexibles
    cuotas = db.Column(db.JSON) # { "1": 1.5, "X": 3.0... }
    prediccion = db.Column(db.JSON) # Snapshot de la predicción
    info_extra = db.Column(db.JSON) # { "estadio": "Bernabeu", "arbitro": "..." }
    
    # Relaciones
    equipo_local = db.relationship('Equipo', foreign_keys=[id_local, id_liga], lazy='joined',
                                  primaryjoin="and_(Partido.id_local==Equipo.id, Partido.id_liga==Equipo.id_liga)",
                                  overlaps="liga,partidos")
    equipo_visitante = db.relationship('Equipo', foreign_keys=[id_visitante, id_liga], lazy='joined',
                                      primaryjoin="and_(Partido.id_visitante==Equipo.id, Partido.id_liga==Equipo.id_liga)",
                                      overlaps="equipo_local,liga,partidos")

    def _hydrate_prediction(self, pred_data):
        """
        Ensures the prediction JSON has the complete structure required by strict Android clients.
        Fills missing fields with safe defaults.
        """
        defaults = {
            "goles_esperados": {"local": 0.0, "visitante": 0.0},
            "resultado_1x2": {
                "prediccion": "N/A",
                "probabilidades": {"local": 0.0, "empate": 0.0, "visitante": 0.0},
                "probabilidad_max": 0.0,
                "recomendacion": {"arriesgada": 0, "conservadora": 0, "moderada": 0}
            },
            "btts": {
                "prediccion": "N/A",
                "probabilidad": 0.0,
                "recomendacion": {"arriesgada": 0, "conservadora": 0, "moderada": 0}
            },
            "over25": {
                "prediccion": "N/A",
                "probabilidad": 0.0,
                "recomendacion": {"arriesgada": 0, "conservadora": 0, "moderada": 0}
            }
        }

        if not pred_data or not isinstance(pred_data, dict):
            return defaults

        import copy
        hydrated = copy.deepcopy(defaults)
        
        # Manually update to be safe and explicit
        if "goles_esperados" in pred_data:
            hydrated["goles_esperados"].update(pred_data["goles_esperados"])
            
        if "resultado_1x2" in pred_data:
            src = pred_data["resultado_1x2"]
            tgt = hydrated["resultado_1x2"]
            if "prediccion" in src: tgt["prediccion"] = src["prediccion"]
            if "probabilidad_max" in src: tgt["probabilidad_max"] = src["probabilidad_max"]
            if "probabilidades" in src: tgt["probabilidades"].update(src["probabilidades"])
            if "recomendacion" in src: tgt["recomendacion"].update(src["recomendacion"])

        if "btts" in pred_data:
            src = pred_data["btts"]
            tgt = hydrated["btts"]
            if "prediccion" in src: tgt["prediccion"] = src["prediccion"]
            if "probabilidad" in src: tgt["probabilidad"] = src["probabilidad"]
            if "recomendacion" in src: tgt["recomendacion"].update(src["recomendacion"])

        if "over25" in pred_data:
            src = pred_data["over25"]
            tgt = hydrated["over25"]
            if "prediccion" in src: tgt["prediccion"] = src["prediccion"]
            if "probabilidad" in src: tgt["probabilidad"] = src["probabilidad"]
            if "recomendacion" in src: tgt["recomendacion"].update(src["recomendacion"])

        return hydrated

    def to_dict(self):
        c = self.cuotas or {}
        i = self.info_extra or {}
        
        # Hydrate prediction for strict clients
        pred_hydrated = self._hydrate_prediction(self.prediccion)
            
        return {
            'id_partido': self.id,
            'estado': self.estado,
            'id_liga': self.id_liga,
            'temporada': self.temporada,
            'jornada': self.jornada,
            # Equipos (nombres)
            'equipo_local': self.equipo_local.nombre if self.equipo_local else "Equipo no encontrado",
            'equipo_visitante': self.equipo_visitante.nombre if self.equipo_visitante else "Equipo no encontrado",
            
            # Estadísticas completas
            'estadisticas_local': self.equipo_local.to_dict() if self.equipo_local else {},
            'estadisticas_visitante': self.equipo_visitante.to_dict() if self.equipo_visitante else {},
            
            'fecha': self.fecha.strftime("%Y-%m-%d") if self.fecha else "1970-01-01", 
            'hora': self.hora or "00:00",
            
            # Flattens info extra
            'ciudad': i.get('ciudad', "Ciudad desconocida"),
            'estadio': i.get('estadio', "Estadio desconocido"),
            'arbitro': i.get('arbitro', "Árbitro no disponible"),
            
            # Flattens cuotas
            'cuota_local': c.get('1', -1),
            'cuota_empate': c.get('X', -1),
            'cuota_visitante': c.get('2', -1),
            'cuota_over': c.get('O25', -1),
            'cuota_under': c.get('U25', -1),
            'cuota_btts': c.get('BTTS', -1),
            'cuota_btts_no': c.get('BTTS_NO', -1),
            
            # Marcadores
            'goles_local': self.goles_local if self.goles_local is not None else -1,
            'goles_visitante': self.goles_visitante if self.goles_visitante is not None else -1,
            'resultado': self.resultado if self.resultado is not None else -1,
            
            # Calculados (ahora explícitos en BD, fallback a cálculo si es None)
            'ambos_marcan': self.ambos_marcan if self.ambos_marcan is not None else i.get('ambos_marcan', -1),
            'local_marca': self.local_marca if self.local_marca is not None else i.get('local_marca', -1),
            'visitante_marca': self.visitante_marca if self.visitante_marca is not None else i.get('visitante_marca', -1),
            'mas_2_5': self.mas_2_5 if self.mas_2_5 is not None else i.get('mas_2_5', -1),
            
            'prediccion': pred_hydrated
        }

# --- Nuevas Tablas para Migración Pickle -> SQL (Fase 4) ---

class CuotaCaliente(db.Model):
    __tablename__ = "cuotas_calientes"
    id = db.Column(db.Integer, primary_key=True) # ID Autoincremental interno
    
    # Vinculación con el partido
    partido_id = db.Column(db.Integer, db.ForeignKey('partidos.id'), nullable=False)
    fecha_detectado = db.Column(db.Date, nullable=False) # Fecha en la que se detectó/guardó
    
    # Datos de la oportunidad (Pick)
    mercado = db.Column(db.String(50))     # 'Ganador', 'BTTS', 'Over 2.5'
    prediccion = db.Column(db.String(50))  # 'Local', 'Si', 'Over', etc.
    probabilidad = db.Column(db.Float)
    cuota = db.Column(db.Float)
    valor = db.Column(db.Float)
    score = db.Column(db.Float)            # Puntuación calculated (para ranking)
    
    # Relación
    partido = db.relationship('Partido', backref=db.backref('cuotas_calientes', lazy=True))

    def to_dict(self):
        return {
            "mercado": self.mercado,
            "prediccion": self.prediccion,
            "prob": self.probabilidad,
            "cuota": self.cuota,
            "value": self.valor,
            "score": self.score
        }

class Reporte(db.Model):
    """
    Tabla para almacenar reportes JSON que antes iban a .pkl
    Claves esperadas: 'precision_global', 'precision_tipo_apuesta', 'resumen_cuotas_calientes'
    """
    __tablename__ = "reportes"
    clave = db.Column(db.String(100), primary_key=True)
    contenido = db.Column(db.JSON)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return self.contenido
