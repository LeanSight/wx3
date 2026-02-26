# Metodologia: ATDD + TDD + One-Piece-Flow

## Principios

1. **ATDD primero**: el acceptance test describe el comportamiento deseado
   desde afuera del sistema (como lo ve el usuario o el pipeline completo).
   Se escribe en RED antes de tocar produccion.

2. **TDD hacia adentro**: para implementar lo que el AT exige, se escriben
   unit tests en RED (test_context, test_pipeline, test_steps, test_cli)
   antes de escribir el codigo de produccion.

3. **Red-Green-Refactor estricto**: ningun cambio de produccion sin test en
   RED previo. El refactor solo ocurre cuando todos los tests son GREEN.

4. **One-piece-flow**: el trabajo se divide en slices verticales minimos.
   Cada slice atraviesa todas las capas necesarias (test + produccion) y
   termina en GREEN antes de abrir el siguiente.

5. **Commit + push por slice**: cada slice completo (GREEN + refactor) genera
   un commit atomico con mensaje descriptivo y se pushea antes de avanzar.

---

## Ciclo por slice

```
1. Identificar el comportamiento del slice (una sola cosa)
2. Escribir AT en test_acceptance.py -> RED
3. Escribir unit tests en la capa afectada -> RED
4. Escribir produccion minima para GREEN
5. Refactor si es necesario (tests siguen GREEN)
6. git commit + git push
7. Avanzar al siguiente slice
```

## Reglas

- Un slice = un commit = un push
- Nunca avanzar al slice N+1 si el slice N no esta en GREEN
- Los tests de slices anteriores no deben regresar a RED
- Si un cambio rompe un test existente, corregir el test en el mismo slice
  solo si el comportamiento cambia intencionalmente; de lo contrario,
  diagnosticar y corregir el codigo de produccion
