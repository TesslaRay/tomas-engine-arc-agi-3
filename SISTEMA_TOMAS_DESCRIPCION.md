# Sistema TOMAS - Descripción Detallada del Funcionamiento

## 📋 Resumen Ejecutivo

TOMAS es un agente cognitivo que resuelve puzzles de ARC-AGI usando un pipeline de tres LLMs especializados que procesan información secuencialmente, cada uno con roles cognitivos específicos que imitan diferentes aspectos del pensamiento humano.

## 🧠 Arquitectura Cognitiva Tripartita

### 1. **APEIRON** (LLM1) - Percepción y Análisis Sensorial
**Rol:** "Los ojos y el sistema perceptual"
- **Función:** Analizar el estado visual del juego y detectar cambios
- **Input:** Matriz de colores del tablero actual + estado anterior
- **Proceso:** Análisis diferencial para detectar qué cambió entre turnos
- **Output:** Entidades identificadas, cambios detectados, hipótesis causales

### 2. **SOPHIA** (LLM2) - Conocimiento y Reglas del Juego
**Rol:** "La memoria y el conocimiento del mundo"
- **Función:** Interpretar las percepciones usando arquetipos de juegos conocidos
- **Input:** Análisis de APEIRON
- **Proceso:** Clasificar entidades, legislar reglas, construir teorías del juego
- **Output:** Reglas verificadas, teorías sobre objetivos, medios para ganar

### 3. **LOGOS** (LLM3) - Decisión y Acción Estratégica
**Rol:** "La voluntad y la toma de decisiones"
- **Input:** Conocimiento de SOPHIA + percepción de APEIRON + sus propias decisiones anteriores
- **Proceso:** Deliberación estratégica y planificación de acciones
- **Output:** Decisión de acción específica o secuencia de acciones

---

## 🔄 Flujo de Procesamiento Detallado

### **TURNO N - Flujo Completo**

#### **Fase 0: Preparación**
1. **Captura del Estado:** Sistema recibe matriz 64x64 del estado del juego
2. **Análisis Diferencial:** Compara estado actual vs anterior (si existe)
3. **Generación de Imagen:** Convierte matriz a representación visual

#### **Fase 1: APEIRON - Análisis Perceptual** ⏱️ (~10-15 segundos)

**Input que recibe APEIRON:**
- Estado actual del tablero (matriz 64x64)
- Estado anterior del tablero
- Vector Cognitivo Global del turno anterior (si existe)
- Análisis de percepción espacial automatizado

**Proceso cognitivo de APEIRON:**
1. **Análisis Diferencial:** "¿Qué cambió desde el turno anterior?"
2. **Identificación de Entidades:** "¿Qué objetos/figuras veo en el tablero?"
3. **Clasificación Funcional:** "¿Para qué sirve cada objeto?"
4. **Análisis Causal:** "¿Por qué ocurrieron estos cambios?"
5. **Hipótesis de Comportamiento:** "¿Cómo se comportan estos objetos?"

**Output de APEIRON (JSON estructurado):**
```json
{
  "timestamp": "2025-08-05T10:30:00.000Z",
  "causal_narrative_of_turn": "El avatar azul se movió hacia arriba y colisionó con una pared gris...",
  "conceptualized_entities": [
    {
      "entity_id": "BLUE_AVATAR",
      "functional_type": "Game-World",
      "sub_type": "Agent-Controlled",
      "description": "Figura azul controlable por el jugador"
    }
  ],
  "new_turn_learnings": [
    {
      "learning_id": "L-001",
      "description": "Los muros grises bloquean el movimiento del avatar",
      "confidence": 0.95
    }
  ],
  "synthesis_for_next_cycle": "El avatar debe encontrar una ruta alternativa..."
}
```

#### **Fase 2: SOPHIA - Análisis Epistémico** ⏱️ (~15-20 segundos)

**Input que recibe SOPHIA:**
- Toda la respuesta de APEIRON
- Su propio conocimiento acumulado de turnos anteriores

**Proceso cognitivo de SOPHIA:**
1. **Clasificación por Arquetipos:** "¿Qué tipo de objetos de juego son estos?"
   - ¿Es un TOOL (herramienta movible)?
   - ¿Es un OBSTACLE_STATIC (muro fijo)?
   - ¿Es un COLLECTIBLE (objeto a recoger)?
   - ¿Es un GOAL_ZONE (zona objetivo)?

2. **Legislación de Reglas:** "¿Qué reglas del juego puedo establecer?"
   - "Contacto con OBSTACLE_STATIC previene movimiento"
   - "AGENT puede empujar objetos TOOL"

3. **Análisis de Objetivos:** "¿Cuál es la meta del juego?"
   - ¿Es COLLECTION_VICTORY (recoger objetos)?
   - ¿Es DESTINATION_VICTORY (llegar a un lugar)?
   - ¿Qué indica que el juego se puede ganar?

4. **Análisis de Medios:** "¿Qué herramientas tengo para ganar?"
   - Movimientos direccionales del avatar
   - Capacidad de empujar objetos
   - Interacciones con switches/botones

**Output de SOPHIA (JSON estructurado):**
```json
{
  "timestamp": "2025-08-05T10:31:00.000Z",
  "epistemic_analysis": "Basándome en APEIRON, identifico el BLUE_AVATAR como arquetipo AGENT...",
  "archetype_analysis": [
    {
      "archetype": "AGENT",
      "candidate_entities": ["BLUE_AVATAR"],
      "supporting_evidence": "Responde a comandos de movimiento...",
      "confidence": 0.95
    }
  ],
  "verified_game_rules": [
    {
      "rule_id": "R-PHYS-001",
      "rule_statement": "AGENT no puede atravesar OBSTACLE_STATIC",
      "scope": "Universal",
      "supporting_evidence": ["L-001"],
      "confidence": 0.95
    }
  ],
  "global_game_theories": [
    {
      "theory_id": "T-MAIN-001",
      "theory_statement": "El objetivo es mover el AGENT hasta la zona con fondo negro...",
      "victory_hypothesis": "Ganar colocando el avatar en la figura de fondo negro",
      "means_catalog": ["Movimiento direccional del avatar", "Navegación alrededor de obstáculos"],
      "status": "ACTIVE"
    }
  ]
}
```

#### **Fase 3: LOGOS - Deliberación y Acción** ⏱️ (~10-15 segundos)

**Input que recibe LOGOS:**
- Respuesta completa de APEIRON (percepción actual)
- Respuesta completa de SOPHIA (conocimiento del juego)
- Su propia respuesta del turno anterior (continuidad estratégica)

**Proceso cognitivo de LOGOS:**
1. **Evaluación del Estado:** "¿Qué tan seguro estoy del conocimiento actual?"
2. **Selección de Estrategia:**
   - **EXPLORATION:** Si hay mucha incertidumbre
   - **EXPERIMENTATION:** Si hay hipótesis específicas que probar
   - **EXPLOITATION:** Si conozco la solución y debo ejecutarla

3. **Planificación:**
   - ¿Acción única o secuencia de acciones?
   - ¿Qué resultado espero de esta acción?

4. **Toma de Decisión:** Selección de acción específica

**Output de LOGOS (JSON estructurado):**
```json
{
  "timestamp": "2025-08-05T10:32:00.000Z",
  "intent_phase": {
    "cognitive_stance": "EXPLOITATION",
    "plan_objective": "Mover avatar hacia zona objetivo evitando obstáculos"
  },
  "counsel_phase": {
    "strategic_analysis": "Ruta directa bloqueada, necesito ir por la izquierda..."
  },
  "choice_phase": {
    "final_decision": {
      "chosen_plan": "MOVE_LEFT",
      "rationale": "Primer paso para bordear obstáculo"
    }
  },
  "command_phase": {
    "immediate_command": {
      "action": "move_left"
    }
  },
  "predictive_judgment_phase": {
    "expected_outcome": "Avatar se moverá una posición a la izquierda"
  }
}
```

#### **Fase 4: Ejecución y Memoria**
1. **Ejecución de Acción:** Sistema ejecuta la acción decidida
2. **Actualización de Estado:** Captura nuevo estado del juego
3. **Actualización de Memoria:** Guarda todo el Vector Cognitivo Global para el próximo turno

---

## 🎯 Experimento con Personas - Preguntas Clave por Fase

### **Para APEIRON (Percepción):**
*Mostrar matriz de colores 64x64*

**Preguntas:**
1. "¿Qué objetos/figuras ves en esta imagen?"
2. "¿Cómo describirías cada objeto que ves?"
3. "Si esta es la situación después de mover hacia arriba, ¿qué crees que pasó?"
4. "¿Qué objetos parecen que el jugador puede controlar?"
5. "¿Qué objetos parecen fijos/inmovibles?"

**Objetivo:** Entender cómo los humanos procesan visualmente la información del juego.

### **Para SOPHIA (Conocimiento):**
*Dar la descripción de objetos de la fase anterior*

**Preguntas:**
1. "Basándote en estos objetos, ¿a qué tipo de juego se parece esto?"
2. "¿Qué reglas crees que podrían aplicar en este juego?"
3. "¿Cuál crees que podría ser el objetivo del juego?"
4. "¿Qué herramientas/habilidades tiene el jugador para ganar?"
5. "¿Hay algún patrón o tipo de juego que reconozcas?"

**Objetivo:** Entender cómo los humanos clasifican y crean reglas sobre juegos.

### **Para LOGOS (Decisión):**
*Dar percepción + conocimiento de las fases anteriores*

**Preguntas:**
1. "¿Qué acción tomarías en esta situación?"
2. "¿Por qué elegirías esa acción específica?"
3. "¿Qué resultado esperas de esa acción?"
4. "¿Estás explorando, experimentando, o ejecutando un plan conocido?"
5. "¿Planificarías una secuencia de movimientos o solo el siguiente?"

**Objetivo:** Entender el proceso de toma de decisiones humano.

---

## 📊 Métricas del Sistema

### **Rendimiento Temporal:**
- **APEIRON:** 10-15 segundos por turno
- **SOPHIA:** 15-20 segundos por turno  
- **LOGOS:** 10-15 segundos por turno
- **Total por turno:** ~40-50 segundos

### **Flujo de Información:**
- **Entrada:** Matriz 64x64 (4,096 valores)
- **APEIRON → SOPHIA:** ~2,000-5,000 caracteres
- **SOPHIA → LOGOS:** ~3,000-8,000 caracteres
- **APEIRON → LOGOS:** ~2,000-5,000 caracteres
- **Salida:** 1 acción específica

### **Capacidades del Sistema:**
- ✅ Análisis diferencial entre turnos
- ✅ Memoria episódica de acciones anteriores
- ✅ Planificación de secuencias de acciones
- ✅ Clasificación por arquetipos de juegos
- ✅ Construcción de teorías sobre objetivos
- ✅ Continuidad estratégica entre turnos

---

## 🔧 Puntos de Mejora Identificables

### **Para el Experimento Humano:**
1. **¿Los humanos ven lo mismo que APEIRON?**
2. **¿Clasifican objetos igual que SOPHIA?**
3. **¿Toman decisiones similares a LOGOS?**
4. **¿En qué momento difieren más del sistema?**
5. **¿Qué información adicional necesitarían los humanos?**

Esta estructura te permitirá comparar directamente el procesamiento humano vs el sistema TOMAS en cada fase cognitiva.