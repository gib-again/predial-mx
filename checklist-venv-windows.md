# Checklist: Configurar venv en Windows (PowerShell)

## 1. Crear el venv con el Python oficial de Windows
```powershell
# Verifica primero qué Python tienes instalado
C:\Users\<tu-usuario>\AppData\Local\Programs\Python\Python3XX\python.exe --version

# Crea el venv especificando la ruta completa al Python oficial
# (evita usar solo `python` si tienes MSYS2/MinGW instalado)
C:\Users\<tu-usuario>\AppData\Local\Programs\Python\Python3XX\python.exe -m venv .venv
```

## 2. Activar el venv
```powershell
# Si es la primera vez, permite scripts en PowerShell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

# Activa el venv (nota el .\ al inicio)
.\.venv\Scripts\Activate.ps1

# Debes ver (.venv) al inicio del prompt
```

## 3. Verificar que el venv está usando el Python correcto
```powershell
python -c "import sys; print(sys.executable)"
# ✅ Correcto:  ...\.venv\Scripts\python.exe
# ❌ Incorrecto: C:\msys64\... o cualquier ruta fuera del .venv
```

## 4. Actualizar pip y setuptools antes de instalar
```powershell
python -m pip install --upgrade pip setuptools wheel
```

## 5. Instalar el proyecto
```powershell
pip install -e ".[dev]"
```

## 6. Verificar que todo quedó bien
```powershell
pip list       # Lista de dependencias instaladas
pytest         # Corre los tests (si los hay)
```

---

## pyproject.toml mínimo recomendado
```toml
[build-system]
requires = ["setuptools>=68.0", "wheel"]
build-backend = "setuptools.build_meta"   # ← usar este, no _legacy

[tool.setuptools.packages.find]
where = ["src"]   # o ["."] si no usas carpeta src/
```

---

## Troubleshooting frecuente

| Error | Causa | Solución |
|-------|-------|----------|
| `source` no reconocido | Comando de bash, no PowerShell | Usar `.\.venv\Scripts\Activate.ps1` |
| `.venv` no se carga como módulo | Falta el `.\` | Usar `.\.venv\Scripts\Activate.ps1` |
| `BackendUnavailable: setuptools.backends._legacy` | Build-backend incorrecto en pyproject.toml | Cambiar a `setuptools.build_meta` |
| `Unsupported platform: mingw_x86_64` | venv creado con Python de MSYS2 | Recrear venv con Python oficial de Windows |
| No se puede eliminar `.venv` | El venv está activo | Correr `deactivate` primero |



## Ejecución:

# 1. Preparar datos (local, sin API)
python -m scripts.run_pipeline ESTADO --steps download
python -m scripts.run_pipeline ESTADO --steps ocr
python -m scripts.run_pipeline ESTADO --steps master
python -m scripts.run_pipeline ESTADO --steps segment


# 2. Enviar a OpenAI (paginado en sub-batches automáticamente)
python -m scripts.run_pipeline ESTADO --steps extract --batch      
# → Genera N sub-batches, los sube, guarda IDs en data/jalisco/meta/batch_JAL_ids.json

# 3. Consultar estado
python -m scripts.batch_download ESTADO --check

# 4. Descargar resultados cuando estén listos
python -m scripts.batch_download ESTADO   

# 5. Validar
python -m scripts.run_pipeline coahuila --steps validate    
```

Para estados grandes la paginación se ve así:
```
  Requests pendientes: 8550
  Sub-batches generados: 4
    [1] batch_OAX_001.jsonl: 2200 requests
    [2] batch_OAX_002.jsonl: 2200 requests
    [3] batch_OAX_003.jsonl: 2200 requests
    [4] batch_OAX_004.jsonl: 1950 requests