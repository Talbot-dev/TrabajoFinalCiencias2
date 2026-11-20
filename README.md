# Instalación

Asegurate de tener previamente instalado:

- Python 3.10 o superior.
- [uv](https://docs.astral.sh/uv/getting-started/installation/).

## Clonar el repo

```bash
git clone git@github.com:Talbot-dev/TrabajoFinalCiencias2.git
cd TrabajoFinalCiencias2
```

### Crear y activar un entorno virtual

Estando en la ruta del proyecto, ejecuta:

```bash
uv venv
```

y para activar:

**Linux / macOS:**

```bash
source .venv/bin/activate
```

**Windows (PowerShell):**

```powershell
.venv\Scripts\Activate.ps1
```

### Instalar dependencias

Finalmente, desde la raíz del proyecto ejecuta:

```bash
uv pip install -r requirements.txt
```
