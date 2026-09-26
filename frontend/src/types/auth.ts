export interface CurrentUser {
  id: string;
  email: string;
  full_name: string;
  organization_id: string;
  /** Códigos de rol (`salesperson`). Para lógica, no para mostrar. */
  roles: string[];
  /** Etiquetas visibles de esos roles ("Vendedor"). */
  role_names: string[];
  permissions: string[];
  /**
   * Módulos que este usuario puede abrir. Los calcula el backend con los
   * módulos de su organización, así que el frontend no repite la lógica de
   * agrupamiento ni se desactualiza si el administrador la cambia.
   */
  modules: string[];
  /**
   * Si puede otorgar el rol de Administrador. Se esconde esa opción con esto,
   * pero la regla la impone la API: un rol propio con `users.manage` no debe
   * poder ascender a nadie a Administrador, ni a sí mismo.
   */
  can_grant_admin: boolean;
}
