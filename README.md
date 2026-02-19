# Delta-Neutral Funding Rate Arbitrage Bot

Sistema de arbitraje de tasas de financiacion delta-neutral entre **Nado Finance** (Ink L2) y **01 Exchange** (Solana).

Dashboard web + Bot Telegram + Full-Auto | Capital < $1,000 por operacion.

## Aviso importante — Capital pequeno (< $1,000)

Con capital pequeno los parametros son **mas restrictivos** que en configuraciones estandar:

| Parametro | Valor | Razon |
|-----------|-------|-------|
| MAX_POSITION_USD | $500 | No arriesgar mas del 50% del capital total en una posicion |
| MIN_NET_APR_PCT | 35% | Con $500, las fees son 0.18% = $0.90 — necesitas APR alto para que compense |
| MAX_SPREAD_PCT | 0.06% | Spread alto penaliza mucho en capital pequeno |
| MAX_OPEN_POSITIONS | 2 | Mas posiciones = capital fragmentado = ineficiencia |
| LIQ_BUFFER_PCT | 35% | Mas conservador que con capital grande |
| MAX_BREAKEVEN_HOURS | 96h | Solo abrir si recuperas fees en < 4 dias |

### Ejemplo de break-even con $450

```
Capital:          $450
Fees round-trip:  $450 x 0.18% = $0.81
Spread estimado:  $450 x 0.04% = $0.18
Coste total:      $0.99

Funding a 35% APR = $450 x 0.35 / 8760h = $0.018/hora
Break-even:       $0.99 / $0.018 = ~55 horas (2.3 dias)
```

## Arquitectura del sistema

```
                         +------------------+
                         |   Telegram Bot   |
                         | (alertas/control)|
                         +--------+---------+
                                  |
+-------------+    +--------------+--------------+    +-------------+
|  Nado       |<-->|                             |<-->| 01 Exchange |
|  Finance    |    |     bot.py (orquestador)    |    | (API local) |
|  (Ink L2)   |    |                             |    | (Solana)    |
+-------------+    +------+--------+------+------+    +-------------+
                          |        |      |
                   +------+  +-----+  +---+-----+
                   |         |        |          |
              risk_manager  config  state.json  WebSocket
                   |                    |        :8081
                   |               +----+----+
                   +-------------->| Dashboard|
                                   | (HTML)   |
                                   +----------+
```

## Requisitos previos

- Python 3.11+
- Node.js 18+ (para la API local de 01 Exchange)
- Wallet en Ink Network con USDT0 (Rabby o MetaMask configurado para Ink)
- Wallet Phantom en Solana con USDC
- Bot de Telegram creado en @BotFather

## Setup paso a paso

```bash
# 1. Dependencias Python
pip install -r backend/requirements.txt

# 2. Variables de entorno
cp .env.example .env
# Editar .env con tu editor preferido

# 3. API local de 01 Exchange (en terminal separada)
# Descargar: https://github.com/01protocol/zo-ts-rest-api
# Configurar su propio .env con tu clave Solana
node zo-rest-api.js

# 4. Crear directorios de datos
mkdir -p data

# 5. Arrancar bot (MODO SIMULACION por defecto)
cd backend
python bot.py

# 6. Abrir dashboard
# Abrir frontend/index.html en el navegador
# (o: python -m http.server 9000 -d frontend/ y abrir localhost:9000)

# 7. Verificar en Telegram
# Busca tu bot y envia /status
# Deberias recibir confirmacion del sistema online
```

## Primeros 5 comandos para arrancar en simulacion

```bash
pip install -r backend/requirements.txt
cp .env.example .env
mkdir -p data
cd backend && python bot.py &
python -m http.server 9000 -d ../frontend/
```

## Verificar que todo funciona antes de ir a modo real

- [ ] Bot arranca sin errores
- [ ] Telegram responde a /status
- [ ] Dashboard se conecta al WebSocket (sin banner OFFLINE)
- [ ] Se detectan oportunidades en la tabla
- [ ] En Telegram llegan alertas de oportunidades
- [ ] Prueba `/open ETH-PERP 300` — debe simular apertura y notificar
- [ ] Prueba `/close ETH-001` — debe simular cierre y notificar
- [ ] El funding se acumula correctamente en la posicion simulada
- [ ] Los 3 stops funcionan: prueba manualmente modificando datos mock
- [ ] El sistema ha corrido 24h+ sin caerse ni errores

## Como pasar a modo real

1. Completar todos los puntos del checklist anterior
2. Depositar USDT0 en Nado (Ink Network) y USDC en 01 Exchange
3. Cambiar `DRY_RUN=false` en `.env`
4. Reiniciar el bot
5. Confirmar cambio via Telegram: el bot pedira confirmacion explicita
6. Operar la primera posicion con el minimo ($150-$200) para verificar ejecucion real

## Comandos de Telegram

| Comando | Descripcion |
|---------|-------------|
| `/status` | Estado sistema, posiciones activas, PnL, modo DRY/REAL |
| `/opportunities` | Lista ordenada por Net APR con scores |
| `/positions` | Tabla detallada de posiciones abiertas |
| `/open <par> <capital>` | Abrir posicion manual (ej: `/open ETH-PERP 400`) |
| `/close <id>` | Cerrar posicion (ej: `/close ETH-001`) |
| `/closeall` | Cerrar todas (con confirmacion) |
| `/pause` | Pausar apertura de nuevas posiciones |
| `/resume` | Reanudar |
| `/risk` | Ver parametros de riesgo actuales |
| `/setrisk <param> <valor>` | Modificar parametro en caliente |
| `/dryrun on\|off` | Cambiar modo (requiere confirmacion para modo real) |
| `/help` | Lista de comandos |

## Hotkeys del Dashboard

| Tecla | Accion |
|-------|--------|
| `R` | Refresh manual |
| `O` | Focus en calculadora |
| `P` | Toggle pause/resume |
| `Escape` | Cerrar modal activo |

## Reglas de riesgo activas

1. **Funding invierte signo**: Si el funding rate se vuelve negativo 3 veces consecutivas, cierre automatico inmediato.
2. **Stop loss por PnL**: Si el PnL neto cae por debajo de -3% del capital desplegado, cierre automatico.
3. **Maximo posiciones simultaneas**: Maximo 2 posiciones abiertas al mismo tiempo.
4. **Alerta de liquidacion**: Si la distancia al precio de liquidacion es menor al 35%, alerta critica via Telegram (no cierre automatico).
5. **Posicion expirada**: Cierre automatico si una posicion supera las 120 horas (5 dias).

## Fees verificadas (Feb 2026)

| Protocolo | Maker | Taker | Funding | Red |
|-----------|-------|-------|---------|-----|
| Nado | -0.01% | +0.04% | Cada 1h | Ink L2 |
| 01 Exchange | +0.02% | +0.05% | Cada 1h | Solana |
| **Round-trip** | | **+0.18%** | | |

## Riesgos inherentes (LEER OBLIGATORIAMENTE)

- **Funding puede invertirse repentinamente** — el bot cierra, pero puede haber slippage
- **Liquidacion de una pierna** antes de que el bot cierre la otra — perdida asimetrica
- **Slippage** al operar en dos protocolos distintos no simultaneamente
- **Riesgo smart contract** de Nado (Ink L2) y 01 Exchange (Solana)
- **Congestion de red** Solana o Ink puede retrasar ordenes criticas
- **La API local de 01** debe estar corriendo siempre — si se cae, el bot entra en mock_mode

## Limitaciones conocidas y mejoras para fase 2

- **Fase 2**: Soporte para mas pares (BNB-PERP, XRP-PERP)
- **Fase 2**: Balanceo automatico de colateral entre protocolos
- **Fase 2**: Integracion con mas DEXes (dYdX, Hyperliquid)
- **Fase 2**: Backtesting con datos historicos de funding
- **Fase 2**: Dashboard con autenticacion y multi-usuario
- **Limitacion**: Los precios de liquidacion son estimados, no exactos
- **Limitacion**: No hay rebalanceo automatico si una pierna se desvia
- **Limitacion**: El WebSocket de Nado puede desconectarse en periodos de alta volatilidad

## Estructura de archivos

```
bsb-capital/
├── backend/
│   ├── bot.py                 # Motor principal
│   ├── config.py              # Configuracion y parametros
│   ├── risk_manager.py        # Gestion de riesgo
│   ├── nado_client.py         # Cliente Nado Finance (async)
│   ├── exchange01_client.py   # Cliente 01 Exchange (local)
│   ├── telegram_bot.py        # Bot Telegram
│   └── requirements.txt       # Dependencias Python
├── frontend/
│   └── index.html             # Dashboard web (autocontenido)
├── data/                      # Persistencia (gitignored)
│   ├── positions.json
│   ├── history.json
│   └── state.json
├── .env.example               # Plantilla de variables
├── .gitignore
└── README.md
```
