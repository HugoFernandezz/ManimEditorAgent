# Outline — "¿Qué es el determinante?" (30 s, ES, Bachillerato)

> Solo ManimCE (Community Edition). Sin plugins externos.
> Duración objetivo: 30 s · margen ±20 % → rango aceptable 24 – 36 s.

---

## Scene 1 — La pregunta que nadie responde bien

**Duración estimada:** 5 s

**Descripción visual:**
Fondo negro. Con `Write`, aparece el título grande centrado:
`"El Determinante"`.
Medio segundo después, debajo, `FadeIn` sobre la matriz 2 × 2 en `MathTex`:

$$\det\begin{pmatrix}a & b \\ c & d\end{pmatrix} = ad - bc$$

El coder debe usar `MathTex` (no `Tex`) para la expresión. La fórmula se queda pantalla mientras el narrador plantea la pregunta.

**Momento clave:**
Mostrar la fórmula cruda al alumno y dejar abierta la tensión: *¿por qué diablos se restan esos productos?*

---

## Scene 2 — El espacio se transforma

**Duración estimada:** 11 s

**Descripción visual:**
Usar `LinearTransformationScene` (clase built-in de ManimCE, hereda de `VectorScene`).

1. `self.add_transformable_mobject` sobre un `Square` (unidad, vértices en (0,0), (1,0), (1,1), (0,1)) pintado semitransparente en azul.
2. Mostrar los dos vectores base î (verde) y ĵ (rojo) con `self.add_vector`.
3. Llamar `self.apply_matrix(np.array([[2, 1], [0, 2]]))` con `run_time=3`:
   - La cuadrícula se deforma.
   - El cuadrado azul se convierte en un **paralelogramo**.
   - î y ĵ se mueven a sus nuevas posiciones (2,0) y (1,2).
4. `self.wait(1)` con el resultado congelado en pantalla.

El animator debe configurar `include_background_plane=True` y `background_plane_kwargs` para que la cuadrícula deformada sea visible sin saturar la escena.

**Momento clave:**
La transformación lineal es una *máquina que deforma el espacio*. El cuadrado unidad deja de ser cuadrado — pero algo cuantificable ha cambiado.

---

## Scene 3 — El determinante mide el área

**Duración estimada:** 9 s

**Descripción visual:**
Continuación directa de la escena anterior (o fundido rápido a nueva escena).

1. Rellenar el paralelogramo resultante con un color sólido semitransparente (amarillo) usando `Polygon` sobre las cuatro esquinas transformadas: (0,0), (2,0), (3,2), (1,2).
2. Añadir un `Brace` en la base del paralelogramo con label `"base = 2"` y otro `Brace` lateral con `"altura = 2"`.
3. `FadeIn` del texto:

   $$\text{Área} = 2 \times 2 = 4 = \det\!\begin{pmatrix}2 & 1 \\ 0 & 2\end{pmatrix}$$

4. Resaltar `"4"` con un recuadro (`SurroundingRectangle`) y, justo al lado, un texto pequeño: `"× 4 el área original"`.

**Verificación matemática:**
`det([[2,1],[0,2]]) = 2·2 − 1·0 = 4`. El cuadrado unidad tiene área 1; el paralelogramo resultante tiene área 4. ✓

**Momento clave:**
El determinante **es** el factor por el que la transformación escala las áreas. No una fórmula arbitraria — una medida geométrica concreta.

---

## Scene 4 — Det = 0: el espacio colapsa

**Duración estimada:** 5 s

**Descripción visual:**
Transición rápida. Nueva `LinearTransformationScene` (o misma escena con reset).

1. Mostrar el cuadrado unidad de nuevo, fresco.
2. Aplicar `self.apply_matrix(np.array([[1, 2], [0.5, 1]]))` con `run_time=2`.
   - El cuadrado se aplana completamente sobre la línea `y = 0.5x`.
3. `FadeIn` texto centrado en rojo:

   $$\det\begin{pmatrix}1 & 2 \\ 0{,}5 & 1\end{pmatrix} = 1\cdot1 - 2\cdot0{,}5 = 0$$

4. Una línea abajo, `Write` el mensaje final: `"det = 0 → el espacio colapsa a una línea"`.

**Verificación matemática:**
`det([[1,2],[0.5,1]]) = 1·1 − 2·0.5 = 1 − 1 = 0` ✓. Las columnas son linealmente dependientes: [1, 0.5] = 0.5·[2,1], por lo que la imagen del plano es una recta.

**Momento clave:**
Cuando el determinante es cero la transformación destruye una dimensión — toda el área desaparece. Es la señal algebraica de que la matriz **no es invertible**.

---

## Resumen de duraciones

| # | Escena | Duración |
|---|--------|----------|
| 1 | La pregunta que nadie responde bien | 5 s |
| 2 | El espacio se transforma | 11 s |
| 3 | El determinante mide el área | 9 s |
| 4 | Det = 0: el espacio colapsa | 5 s |
| | **Total** | **30 s** |

---

## Notas de implementación para el Coder

- Usar `LinearTransformationScene` (importada de `manim`) en las escenas 2 y 4 — evita construir la cuadrícula y los vectores base a mano.
- La matriz debe pasarse como `np.array` 2 × 2; `LinearTransformationScene.apply_matrix` lo extiende internamente a 3D.
- Usar `MathTex` en todos los contextos matemáticos, nunca `Tex`.
- Posicionar labels con `.next_to()` y `.to_edge()` — sin coordenadas mágicas.
- Los `wait()` entre animaciones son obligatorios para que el alumno asimile cada paso; no comprimirlos por debajo de 0.5 s.
- El paralelogramo de la escena 3 debe construirse con `Polygon(A, B, C, D).set_fill(YELLOW, opacity=0.4).set_stroke(YELLOW, width=2)`, usando las coordenadas transformadas exactas.