export interface CurrentUser {
  id: string;
  email: string;
  full_name: string;
  organization_id: string;
  roles: string[];
  permissions: string[];
}
