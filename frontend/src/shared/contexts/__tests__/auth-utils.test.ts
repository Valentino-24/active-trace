import { describe, it, expect } from 'vitest';
import { hasPermission } from '../auth-utils';

describe('auth-utils', () => {
  it('hasPermission returns true when permission is in list', () => {
    const permissions = ['calificaciones:importar', 'equipos:gestionar'];
    expect(hasPermission(permissions, 'calificaciones:importar')).toBe(true);
  });

  it('hasPermission returns false when permission is missing', () => {
    const permissions = ['calificaciones:importar'];
    expect(hasPermission(permissions, 'equipos:gestionar')).toBe(false);
  });

  it('hasPermission returns false for empty list', () => {
    expect(hasPermission([], 'equipos:gestionar')).toBe(false);
  });

  it('hasPermission handles undefined permissions', () => {
    expect(hasPermission(undefined, 'test')).toBe(false);
  });
});
