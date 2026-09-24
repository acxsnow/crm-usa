import { createBrowserRouter } from "react-router-dom";
import { LoginPage } from "@/features/auth/LoginPage";
import { ForgotPasswordPage } from "@/features/auth/ForgotPasswordPage";
import { ResetPasswordPage } from "@/features/auth/ResetPasswordPage";
import { AcceptInvitationPage } from "@/features/auth/AcceptInvitationPage";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { RequireAccess } from "@/components/RequireAccess";
import { MODULE } from "@/config/navigation";
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
          <RequireAccess module={MODULE.CUSTOMERS} moduleLabel="Prospectos y clientes">
            <CustomersPage />
          </RequireAccess>
        ),
      },
      {
        path: "customers/:customerId",
        element: (
          <RequireAccess module={MODULE.CUSTOMERS} moduleLabel="Prospectos y clientes">
            <CustomerDetailPage />
          </RequireAccess>
        ),
      },
      {
        path: "applications/new",
        element: (
          <RequireAccess module={MODULE.CASES} moduleLabel="Expedientes">
            <ApplicationPage />
          </RequireAccess>
        ),
      },
      {
        path: "applications",
        element: (
          <RequireAccess module={MODULE.CASES} moduleLabel="Expedientes">
            <ApplicationsAdminPage />
          </RequireAccess>
        ),
      },
      {
        path: "opportunities",
        element: (
          <RequireAccess module={MODULE.CASES} moduleLabel="Expedientes">
            <OpportunitiesPage />
          </RequireAccess>
        ),
      },
      {
        path: "projects",
        element: (
          <RequireAccess module={MODULE.PROJECTS} moduleLabel="Proyectos e instalación">
            <ProjectsPage />
          </RequireAccess>
        ),
      },
      {
        path: "projects/:projectId",
        element: (
          <RequireAccess module={MODULE.PROJECTS} moduleLabel="Proyectos e instalación">
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
          <RequireAccess module={MODULE.BILLING} moduleLabel="Facturación y cobros">
            <InvoicesPage />
          </RequireAccess>
        ),
      },
      {
        path: "users",
        element: (
          <RequireAccess module={MODULE.TEAM} moduleLabel="Usuarios y roles">
            <UsersPage />
          </RequireAccess>
        ),
      },
      {
        path: "audit-log",
        element: (
          <RequireAccess module={MODULE.AUDIT} moduleLabel="Auditoría">
            <AuditLogPage />
          </RequireAccess>
        ),
      },
    ],
  },
]);
