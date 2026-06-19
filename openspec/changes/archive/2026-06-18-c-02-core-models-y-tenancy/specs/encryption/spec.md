## ADDED Requirements

### Requirement: Cifrado AES-256 de atributos PII

El sistema SHALL proveer una utilidad de cifrado AES-256-GCM para almacenar atributos PII (CBU, DNI, email) en reposo.

#### Scenario: Cifrado round-trip exitoso

- **WHEN** un texto plano se cifra con la clave de cifrado
- **THEN** el resultado es un string en base64
- **AND** al descifrar ese resultado con la misma clave se obtiene el texto original

#### Scenario: Descifrado con clave incorrecta falla

- **WHEN** se intenta descifrar un valor cifrado con una clave diferente
- **THEN** la operación falla con un error de autenticación

#### Scenario: Descifrado de datos corruptos falla

- **WHEN** se intenta descifrar un string base64 inválido o corrupto
- **THEN** la operación falla con un error
