import { createBrowserRouter } from "react-router-dom";
import { LoginPage } from "@/features/auth/LoginPage";
import { ForgotPasswordPage } from "@/features/auth/ForgotPasswordPage";
import { ResetPasswordPage } from "@/features/auth/ResetPasswordPage";
import { AcceptInvitationPage } from "@/features/auth/AcceptInvitationPage";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { RequireAccess } from "@/components/RequireAccess";
import { DashboardLayout } from "@/app/DashboardLayout";
import { DashboardHome } from "@/app/DashboardHome";
import { LeadsPage } from "@/features/crm/LeadsPage";
import { CustomersPage } from "@/features/crm/CustomersPage";
import { CustomerDetailPage } from "@/features/crm/CustomerDetailPage";
import { OpportunitiesPage } from "@/features/crm/OpportunitiesPage";
import { ProjectsPage } from "@/features/field-ops/ProjectsPage";
import { ProjectDetailPage } from "@/features/field-ops/ProjectDetailPage";
import { TechnicianMonitorPage } from "@/features/field-ops/TechnicianMonitorPage";
import { InvoicesPage } from "@/features/billing/InvoicesPage";
import { UsersPage } from "@/features/users/UsersPage";
import { AuditLogPage } from "@/features/audit/AuditLogPage";
import { RolesPage } from "@/features/roles/RolesPage";
import { CustomerSignaturePage } from "@/features/field-ops/CustomerSignaturePage";
import { ApplicationPage } from "@/features/crm/ApplicationPage";
import { ApplicationsAdminPage } from "@/features/crm/ApplicationsAdminPage";

/**
 * Cada ruta declara qué módulo o permiso la habilita.
 *
 * Sin esto, cualquier usuario con sesión podía abrir `/invoices` o `/users`
 * escribiendo la dirección: la API rechazaba cada consulta con 403, pero la
 * pantalla se montaba igual y quedaba una tabla vacía sin explicación.
 */
export const router = createBrowserRouter([
  { path: "/login", element: <LoginPage /> },
  { path: "/forgot-password", element: <ForgotPasswordPage /> },
  { path: "/reset-password", element: <ResetPasswordPage /> },
  { path: "/accept-invitation", element: <AcceptInvitationPage /> },
  { path: "/customer-signature", element: <CustomerSignaturePage /> },
  {
    path: "/",
    element: (
      <ProtectedRoute>
        <DashboardLayout />
      </ProtectedRoute>
    ),
    children: [
      { index: true, element: <DashboardHome /> },
      {
        path: "leads",
        element: (
          <RequireAccess permission="leads.manage" moduleLabel="Prospectos">
            <LeadsPage />
          </RequireAccess>
        ),
      },
      {
        path: "customers",
        element: (
          <RequireAccess permission="customers.read" moduleLabel="Clientes">
            <CustomersPage />
          </RequireAccess>
        ),
      },
      {
        path: "customers/:customerId",
        element: (
          <RequireAccess permission="customers.read" moduleLabel="Clientes">
            <CustomerDetailPage />
          </RequireAccess>
        ),
      },
      {
        path: "applications/new",
        element: (
          <RequireAccess permission="cases.create" moduleLabel="la creación de expedientes">
            <ApplicationPage />
          </RequireAccess>
        ),
      },
      {
        path: "applications",
        element: (
          <RequireAccess permission={["cases.read_own", "cases.read_all"]} moduleLabel="Expedientes">
            <ApplicationsAdminPage />
          </RequireAccess>
        ),
      },
      {
        path: "opportunities",
        element: (
          <RequireAccess permission="opportunities.manage" moduleLabel="el Pipeline">
            <OpportunitiesPage />
          </RequireAccess>
        ),
      },
      {
        path: "projects",
        element: (
          <RequireAccess permission={["projects.read_all", "projects.read_assigned"]} moduleLabel="Proyectos e instalación">
            <ProjectsPage />
          </RequireAccess>
        ),
      },
      {
        path: "projects/:projectId",
        element: (
          <RequireAccess permission={["projects.read_all", "projects.read_assigned"]} moduleLabel="Proyectos e instalación">
            <ProjectDetailPage />
          </RequireAccess>
        ),
      },
      {
        path: "technician-monitor",
        element: (
          <RequireAccess permission="dashboards.operations" moduleLabel="el monitor de técnicos">
            <TechnicianMonitorPage />
          </RequireAccess>
        ),
      },
      {
        path: "invoices",
        element: (
          <RequireAccess permission="invoices.read" moduleLabel="Facturación y cobros">
            <InvoicesPage />
          </RequireAccess>
        ),
      },
      {
        path: "users",
        element: (
          <RequireAccess permission="users.manage" moduleLabel="Usuarios y roles">
            <UsersPage />
          </RequireAccess>
        ),
      },
      {
        path: "roles",
        element: (
          <RequireAccess permission="roles.manage" moduleLabel="Roles y permisos">
            <RolesPage />
          </RequireAccess>
        ),
      },
      {
        path: "audit-log",
        element: (
          <RequireAccess permission="audit.read" moduleLabel="Auditoría">
            <AuditLogPage />
          </RequireAccess>
        ),
      },
    ],
  },
]);
