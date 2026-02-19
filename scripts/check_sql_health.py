import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app import create_app
from extensions import db
from models import Partido, Equipo, Liga
from datetime import date

app = create_app()

def check_v1_health():
    with app.app_context():
        print("\n=== RDScore DB Health Check (v1) ===")
        
        # 1. Resumen de Tablas
        n_ligas = Liga.query.count()
        n_equipos = Equipo.query.count()
        n_partidos = Partido.query.count()
        print(f"Ligas: {n_ligas}")
        print(f"Equipos: {n_equipos}")
        print(f"Partidos: {n_partidos}")

        # 2. Análisis de Partidos
        hoy = date.today()
        pasados = Partido.query.filter(Partido.fecha < hoy).count()
        hoy_futuros = Partido.query.filter(Partido.fecha >= hoy).count()
        con_pred = Partido.query.filter(Partido.prediccion.isnot(None)).count()
        
        print(f"\nDistribucción de Partidos:")
        print(f"  - Pasados: {pasados}")
        print(f"  - Hoy/Futuros: {hoy_futuros}")
        print(f"  - Con Predicción: {con_pred}")

        # 3. Verificación de Claves Compuestas (Equipos)
        # Buscar equipos que aparezcan en más de una liga
        from sqlalchemy import func
        duplicados = db.session.query(Equipo.id, func.count(Equipo.id_liga)).group_by(Equipo.id).having(func.count(Equipo.id_liga) > 1).limit(5).all()
        
        if duplicados:
            print(f"\nEquipos Multi-Competición detectados (OK):")
            for id_eq, count in duplicados:
                nombres = [e.nombre for e in Equipo.query.filter_by(id=id_eq).all()]
                print(f"  - ID {id_eq}: Aparece en {count} ligas ({', '.join(set(nombres))})")
        else:
            print("\nNota: No se detectaron equipos compartidos entre ligas (normal si solo has migrado ligas principales).")

        # 4. Verificar Integrity Error (Partidos sin equipo local asignado por error de carga)
        # Esto es lo que fallaba antes. Comprobamos si hay partidos "huérfanos".
        huerfanos = 0
        ejemplo_partido = Partido.query.first()
        if ejemplo_partido:
             # Una forma rápida de ver si la relación falla es intentar acceder al nombre
             invalidos = [p.id for p in Partido.query.limit(100).all() if p.equipo_local is None]
             if invalidos:
                 print(f"\n⚠️ Alerta: Se han detectado partidos huérfanos (sin equipo vinculado): {len(invalidos)} de los primeros 100.")
             else:
                 print("\n✅ Integridad de relaciones: OK (Los partidos están vinculados correctamente a sus equipos).")

if __name__ == "__main__":
    check_v1_health()