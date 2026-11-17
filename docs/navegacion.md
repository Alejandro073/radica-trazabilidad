# Diagrama de navegación y mapa de pantallas

```mermaid
flowchart TD
    L[Ingresar] --> P[Panel]
    P --> LC[Lista de cuentas]
    P --> N[Nueva cuenta<br/>Admisión]
    P --> I[Indicadores<br/>Facturación · Auditoría · Admin]
    P --> A[Administración<br/>solo Administrador]
    LC --> D[Detalle de cuenta]
    N --> D
    D --> S[Cargar soporte]
    D --> V[Validar documentación]
    D --> R[Radicar]
    D --> G[Registrar / responder glosa]
    D --> T[Línea de tiempo]
    P --> X[Salir]
```

| Pantalla | Ruta | Roles |
|---|---|---|
| Ingreso | `/ingresar/` | Todos |
| Panel | `/` | Todos |
| Lista de cuentas | `/cuentas/` | Todos (Admisión: solo las propias) |
| Nueva cuenta | `/cuentas/nueva/` | Admisión, Administrador |
| Detalle de cuenta | `/cuentas/<id>/` | Todos (con alcance) |
| Indicadores | `/indicadores/` | Facturación, Auditoría, Administrador |
| Administración | `/admin/` | Administrador |

Los *mockups* de alta fidelidad (Figma) se generan a partir de estas pantallas; las capturas de la versión implementada están en la carpeta `docs/capturas/` (agregar tras la primera ejecución).
