export function hasPermission(permissions: string[] | undefined, required: string): boolean {
  if (!permissions) return false;
  return permissions.includes(required);
}
