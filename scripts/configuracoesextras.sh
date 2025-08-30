#!/usr/bin/env bash
set -Eeuo pipefail

SERVICE="${1:-}"
if [[ -z "${SERVICE}" ]]; then
  echo "[configuracoesextras] Uso: configuracoesextras.sh <servico>" >&2
  exit 1
fi

log()        { echo -e "[configuracoesextras][${SERVICE}] $*"; }
log_success(){ echo -e "[OK][${SERVICE}] $*"; }
log_warn()   { echo -e "[WARN][${SERVICE}] $*"; }
log_error()  { echo -e "[ERROR][${SERVICE}] $*" >&2; }

# Detect python binary available in the container
PYTHON_BIN="python"
if ! command -v "${PYTHON_BIN}" >/dev/null 2>&1; then
  PYTHON_BIN="python3"
fi

# Detect a usable pip command (python -m pip, pip, pip3, or venv pip). Try ensurepip if needed.
PIP_CMD=""
detect_pip() {
  # Prefer system Python to avoid Superset's internal venv (/app/.venv)
  local sys_pys=(
    "/usr/local/bin/python3"
    "/usr/bin/python3"
    "/usr/local/bin/python"
    "/usr/bin/python"
  )
  local py=""
  for cand in "${sys_pys[@]}"; do
    if [ -x "$cand" ]; then
      py="$cand"
      break
    fi
  done
  if [ -z "$py" ]; then
    py="${PYTHON_BIN}"
  fi

  # Try pip via system Python
  if bash -lc "$py -m pip --version >/dev/null 2>&1"; then
    PIP_CMD="$py -m pip"
    return 0
  fi

  # Try to bootstrap pip via ensurepip
  if bash -lc "$py -m ensurepip --upgrade >/dev/null 2>&1"; then
    if bash -lc "$py -m pip --version >/dev/null 2>&1"; then
      PIP_CMD="$py -m pip"
      return 0
    fi
  fi

  # Fallback: bootstrap via get-pip.py
  if command -v curl >/dev/null 2>&1 || command -v wget >/dev/null 2>&1; then
    local TMP="/tmp/get-pip.py"
    if command -v curl >/dev/null 2>&1; then
      curl -fsSL https://bootstrap.pypa.io/get-pip.py -o "$TMP" || true
    else
      wget -qO "$TMP" https://bootstrap.pypa.io/get-pip.py || true
    fi
    if [ -s "$TMP" ]; then
      if "$py" "$TMP" >/dev/null 2>&1; then
        if bash -lc "$py -m pip --version >/dev/null 2>&1"; then
          PIP_CMD="$py -m pip"
          return 0
        fi
      fi
    fi
  fi

  # Last resort: try generic binaries
  local candidates=("pip" "pip3")
  for c in "${candidates[@]}"; do
    if bash -lc "$c --version >/dev/null 2>&1"; then
      PIP_CMD="$c"
      return 0
    fi
  done
  return 1
}

have_module() {
  local module="$1"
  "${PYTHON_BIN}" - <<PY >/dev/null 2>&1
import sys, importlib
try:
    extra_paths = [
        "/app/superset_home/pythonpath",
    ]
    for p in extra_paths:
        if p not in sys.path:
            sys.path.insert(0, p)
except Exception:
    pass
importlib.import_module("${module}")
PY
}

# Ensure a compatibility shim for legacy "sqlalchemy_trino" imports
ensure_sqlalchemy_trino_shim() {
  local TARGET_DIR="/app/superset_home/pythonpath"
  if have_module "trino.sqlalchemy"; then
    if ! have_module "sqlalchemy_trino"; then
      log "Criando shim de compatibilidade 'sqlalchemy_trino' -> 'trino.sqlalchemy'"
      mkdir -p "${TARGET_DIR}/sqlalchemy_trino"
      cat > "${TARGET_DIR}/sqlalchemy_trino/__init__.py" <<'PY'
# Auto-generated shim: sqlalchemy_trino -> trino.sqlalchemy
from trino.sqlalchemy import *  # noqa
try:
    from importlib.metadata import version as _v
    __version__ = _v("sqlalchemy-trino")
except Exception:
    __version__ = "unknown"
PY
    fi
  fi
}

install_trino_superset_deps() {
  # Ensure target dir exists for shim and installs
  local TARGET_DIR="/app/superset_home/pythonpath"
  mkdir -p "${TARGET_DIR}"

  # Check current availability
  local HAVE_TRINO=0 HAVE_SA_TRINO=0 HAVE_TRINO_SA=0
  have_module "trino" && HAVE_TRINO=1 || true
  have_module "sqlalchemy_trino" && HAVE_SA_TRINO=1 || true
  have_module "trino.sqlalchemy" && HAVE_TRINO_SA=1 || true

  # Always ensure compatibility shim when trino.sqlalchemy exists but sqlalchemy_trino doesn't
  if [[ "${HAVE_TRINO_SA}" -eq 1 && "${HAVE_SA_TRINO}" -eq 0 ]]; then
    log "Criando shim de compatibilidade 'sqlalchemy_trino' -> 'trino.sqlalchemy'"
    mkdir -p "${TARGET_DIR}/sqlalchemy_trino"
    cat > "${TARGET_DIR}/sqlalchemy_trino/__init__.py" <<'PY'
# Auto-generated shim: sqlalchemy_trino -> trino.sqlalchemy
from trino.sqlalchemy import *  # noqa
try:
    from importlib.metadata import version as _v
    __version__ = _v("sqlalchemy-trino")
except Exception:
    __version__ = "unknown"
PY
    HAVE_SA_TRINO=1
  fi

  # If we already have a dialect (either) and trino client, we're done
  if { [[ "${HAVE_TRINO_SA}" -eq 1 ]] || [[ "${HAVE_SA_TRINO}" -eq 1 ]]; } && [[ "${HAVE_TRINO}" -eq 1 ]]; then
    log_success "Pacotes já presentes: trino + dialect"
    return 0
  fi

  log "Instalando dependências do Trino para o Superset (sqlalchemy-trino==0.5.0, trino==0.335.0)"
  if detect_pip; then
    log "Usando pip: ${PIP_CMD}"
  else
    log_warn "pip não encontrado e não foi possível inicializar; pulando instalação do driver Trino"
    return 0
  fi

  local PIP_TARGET=(--target "${TARGET_DIR}")
  log "PIP install target: --target ${TARGET_DIR}"

  ${PIP_CMD} install --no-cache-dir --no-deps "${PIP_TARGET[@]}" \
    "sqlalchemy-trino==0.5.0" \
    "trino==0.335.0" || log_warn "Falha ao instalar pacotes Trino"

  # Ensure Trino runtime dependencies available in target
  local MISSING_SIMPLE_DEPS=()
  have_module "lz4.block" || MISSING_SIMPLE_DEPS+=("lz4")
  have_module "zstandard" || MISSING_SIMPLE_DEPS+=("zstandard")
  have_module "tzlocal" || MISSING_SIMPLE_DEPS+=("tzlocal")
  if [ "${#MISSING_SIMPLE_DEPS[@]}" -gt 0 ]; then
    log "Instalando dependências simples do cliente Trino: ${MISSING_SIMPLE_DEPS[*]}"
    ${PIP_CMD} install --no-cache-dir "${PIP_TARGET[@]}" "${MISSING_SIMPLE_DEPS[@]}" || log_warn "Falha ao instalar dependências simples do Trino"
  fi

  # 'requests' precisa das suas dependências (urllib3, certifi, idna, charset-normalizer)
  # portanto não usar --no-deps aqui
  if ! have_module "requests"; then
    log "Instalando 'requests' (com dependências) no target"
    ${PIP_CMD} install --no-cache-dir "${PIP_TARGET[@]}" "requests>=2.27,<3" || log_warn "Falha ao instalar requests"
  fi

  # Ensure shim after install as well
  if have_module "trino.sqlalchemy" && ! have_module "sqlalchemy_trino"; then
    log "Criando shim de compatibilidade 'sqlalchemy_trino' -> 'trino.sqlalchemy'"
    mkdir -p "${TARGET_DIR}/sqlalchemy_trino"
    cat > "${TARGET_DIR}/sqlalchemy_trino/__init__.py" <<'PY'
# Auto-generated shim: sqlalchemy_trino -> trino.sqlalchemy
from trino.sqlalchemy import *  # noqa
try:
    from importlib.metadata import version as _v
    __version__ = _v("sqlalchemy-trino")
except Exception:
    __version__ = "unknown"
PY
  fi

  # Verify
  if { have_module "trino.sqlalchemy" || have_module "sqlalchemy_trino"; } && have_module "trino"; then
    log_success "Instalação concluída do driver Trino"
  else
    log_warn "Falha ao validar instalação do driver Trino"
  fi
}

case "${SERVICE}" in
  superset)
    install_trino_superset_deps
    ;;
  airflow|trino-coordinator|kafka|zookeeper|spark-master|spark-worker|hive-metastore|minio|postgres-airflow|mysql|google-maps-mock)
    log "Nenhuma configuração extra definida para '${SERVICE}'. Pulando."
    ;;
  *)
    log_warn "Serviço desconhecido '${SERVICE}'. Nenhuma ação executada."
    ;;

esac

exit 0
