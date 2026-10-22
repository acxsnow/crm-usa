import { createBrowserRouter } from "react-router-dom";
import { Navigate } from "react-router-dom";
import { LoginPage } from "@/features/auth/LoginPage";
import { ForgotPasswordPage } from "@/features/auth/ForgotPasswordPage";
import { ResetPasswordPage } from "@/features/auth/ResetPasswordPage";
import { AcceptInvitationPage } from "@/features/auth/AcceptInvitationPage";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { RequireAccess } from "@/components/RequireAccess";
import { DashboardLayout } from "@/app/DashboardLayout";
import { DashboardHome } from "@/app/DashboardHome";
import { CustomersPage } from "@/features/crm/CustomersPage";
import { CustomerDetailPage } from "@/features/crm/CustomerDetailPage";
import { ProjectsPage } from "@/features/field-ops/ProjectsPage";
import { REVIEW_INBOX_PERMISSIONS, ReviewInboxPage } from "@/features/review/ReviewInboxPage";
import { ChecklistTemplatesPage } from "@/features/field-ops/ChecklistTemplatesPage";
import { ProjectDetailPage } from "@/features/field-ops/ProjectDetailPage";
import { TechnicianMonitorPage } from "@/features/field-ops/TechnicianMonitorPage";
import { AgendaPage } from "@/features/field-ops/AgendaPage";
import { InvoicesPage } from "@/features/billing/InvoicesPage";
import { ClaimDetailPage } from "@/features/billing/ClaimDetailPage";
import { QuoteDetailPage } from "@/features/billing/QuoteDetailPage";
import { ProgramsPage } from "@/features/programs/ProgramsPage";
import { VersionEditorPage } from "@/features/programs/VersionEditorPage";
import { SalesHomePage } from "@/features/sales/SalesHomePage";
import { VisitPage } from "@/features/sales/VisitPage";
import { CaseFormPage } from "@/features/sales/CaseFormPage";
import { CasesBoardPage } from "@/features/sales/CasesBoardPage";
import { CaseReviewPage } from "@/features/sales/CaseReviewPage";
import { NotificationsPage } from "@/features/notifications/NotificationsPage";
import { CampaignsPage } from "@/features/notifications/CampaignsPage";
import { ExpensesPage } from "@/features/finance/ExpensesPage";
import { PayablesPage } from "@/features/finance/PayablesPage";
import { FinanceClosePage } from "@/features/finance/FinanceClosePage";
import { ReportsPage } from "@/features/finance/ReportsPage";
import { PermitsPage } from "@/features/finance/PermitsPage";
import { UsersPage } from "@/features/users/UsersPage";
import { AuditLogPage } from "@/features/audit/AuditLogPage";
import { RolesPage } from "@/features/roles/RolesPage";
import { CustomerSignaturePage } from "@/features/field-ops/CustomerSignaturePage";
import { WarehouseStockPage } from "@/features/warehouse/WarehouseStockPage";
import { WarehouseItemsPage } from "@/features/warehouse/WarehouseItemsPage";
import { WarehouseReleasesPage } from "@/features/warehouse/WarehouseReleasesPage";
import { WarehouseMovementsPage } from "@/features/warehouse/WarehouseMovementsPage";
import { WarehouseKitsPage } from "@/features/warehouse/WarehouseKitsPage";
import { WarehousePurchasingPage } from "@/features/warehouse/WarehousePurchasingPage";
import { CostTemplatesPage } from "@/features/warehouse/CostTemplatesPage";

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
        path: "projects",
        element: (
          <RequireAccess permission={["projects.read_all", "projects.read_assigned"]} moduleLabel="Proyectos e instalación">
            <ProjectsPage />
          </RequireAccess>
        ),
      },
      {
        path: "review",
        element: (
          <RequireAccess permission={[...REVIEW_INBOX_PERMISSIONS]} moduleLabel="Por revisar">
            <ReviewInboxPage />
          </RequireAccess>
        ),
      },
      // Las colas viven ahora como pestañas de «Por revisar».
      { path: "acta-reviews", element: <Navigate to="/review?tab=actas" replace /> },
      {
        path: "projects/:projectId",
        element: (
          <RequireAccess permission={["projects.read_all", "projects.read_assigned"]} moduleLabel="Proyectos e instalación">
            <ProjectDetailPage />
          </RequireAccess>
        ),
      },
      {
        path: "my-schedule",
        element: (
          <RequireAccess permission={["dispatch.read_own", "dispatch.manage"]} moduleLabel="la agenda">
            <AgendaPage />
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
        path: "sales",
        element: (
          <RequireAccess permission="cases.create" moduleLabel="Mi día">
            <SalesHomePage />
          </RequireAccess>
        ),
      },
      {
        path: "sales/visit",
        element: (
          <RequireAccess permission="cases.create" moduleLabel="las visitas">
            <VisitPage />
          </RequireAccess>
        ),
      },
      {
        path: "cases",
        element: (
          <RequireAccess permission={["cases.read_own", "cases.read_all"]} moduleLabel="Expedientes">
            <CasesBoardPage />
          </RequireAccess>
        ),
      },
      {
        path: "expenses",
        element: (
          <RequireAccess permission={["expenses.create_own", "expenses.read_all", "expenses.approve"]} moduleLabel="Gastos de campo">
            <ExpensesPage />
          </RequireAccess>
        ),
      },
      {
        path: "payables",
        element: (
          <RequireAccess permission={["payables.manage", "suppliers.manage", "payables.approve"]} moduleLabel="Proveedores y pagos">
            <PayablesPage />
          </RequireAccess>
        ),
      },
      {
        path: "finance-close",
        element: (
          <RequireAccess permission={["reconciliation.manage", "profitability.read"]} moduleLabel="Conciliación y rentabilidad">
            <FinanceClosePage />
          </RequireAccess>
        ),
      },
      {
        path: "reports",
        element: (
          <RequireAccess permission={"reports.view"} moduleLabel="Reportes">
            <ReportsPage />
          </RequireAccess>
        ),
      },
      {
        path: "warehouse",
        element: (
          <RequireAccess permission={["warehouse.read", "warehouse.manage", "warehouse.count"]} moduleLabel="Bodega">
            <WarehouseStockPage />
          </RequireAccess>
        ),
      },
      {
        path: "warehouse/items",
        element: (
          <RequireAccess permission={["warehouse.read", "warehouse.manage", "warehouse.count"]} moduleLabel="Bodega">
            <WarehouseItemsPage />
          </RequireAccess>
        ),
      },
      {
        path: "warehouse/releases",
        element: (
          <RequireAccess permission={["warehouse.read", "warehouse.request_release", "warehouse.approve_release",
            "warehouse.deliver", "warehouse.manage"]} moduleLabel="Bodega">
            <WarehouseReleasesPage />
          </RequireAccess>
        ),
      },
      {
        path: "warehouse/movements",
        element: (
          <RequireAccess permission={["warehouse.read", "warehouse.manage", "warehouse.count"]} moduleLabel="Bodega">
            <WarehouseMovementsPage />
          </RequireAccess>
        ),
      },
      {
        path: "warehouse/kits",
        element: (
          <RequireAccess permission={["warehouse.read", "warehouse.kits_manage", "warehouse.manage"]} moduleLabel="Bodega">
            <WarehouseKitsPage />
          </RequireAccess>
        ),
      },
      {
        path: "warehouse/purchasing",
        element: (
          <RequireAccess permission={["budgets.manage", "budgets.approve", "warehouse.read"]} moduleLabel="Bodega">
            <WarehousePurchasingPage />
          </RequireAccess>
        ),
      },
      {
        path: "warehouse/cost-templates",
        element: (
          <RequireAccess permission={["budgets.manage"]} moduleLabel="Bodega">
            <CostTemplatesPage />
          </RequireAccess>
        ),
      },
      {
        path: "permits",
        element: (
          <RequireAccess permission={["permits.manage", "inspections.manage", "projects.read_all"]} moduleLabel="Permisos e inspecciones">
            <PermitsPage />
          </RequireAccess>
        ),
      },
      {
        path: "campaigns",
        element: (
          <RequireAccess permission="notifications.manage" moduleLabel="Campañas">
            <CampaignsPage />
          </RequireAccess>
        ),
      },
      {
        path: "notifications",
        element: (
          <RequireAccess permission={["notifications.read_own", "notifications.manage"]} moduleLabel="Notificaciones">
            <NotificationsPage />
          </RequireAccess>
        ),
      },
      {
        path: "checklists",
        element: (
          <RequireAccess permission="checklists.manage" moduleLabel="Checklists de instalación">
            <ChecklistTemplatesPage />
          </RequireAccess>
        ),
      },
      {
        path: "cases/:caseId/review",
        element: (
          <RequireAccess permission={["cases.review", "cases.approve", "documents.review"]} moduleLabel="la revisión de expedientes">
            <CaseReviewPage />
          </RequireAccess>
        ),
      },
      {
        path: "documents",
        element: <Navigate to="/review" replace />,
      },
      {
        path: "cases/:caseId/form",
        element: (
          <RequireAccess permission={["cases.read_own", "cases.read_all"]} moduleLabel="Expedientes">
            <CaseFormPage />
          </RequireAccess>
        ),
      },
      {
        path: "programs",
        element: (
          <RequireAccess permission="programs.manage" moduleLabel="Configuración de programas">
            <ProgramsPage />
          </RequireAccess>
        ),
      },
      {
        path: "programs/versions/:versionId",
        element: (
          <RequireAccess permission="programs.manage" moduleLabel="Configuración de programas">
            <VersionEditorPage />
          </RequireAccess>
        ),
      },
      {
        path: "invoices/claims/:claimId",
        element: (
          <RequireAccess permission="invoices.read" moduleLabel="Facturación y cobros">
            <ClaimDetailPage />
          </RequireAccess>
        ),
      },
      {
        path: "invoices/quotes/:quoteId",
        element: (
          <RequireAccess permission="quotes.manage" moduleLabel="Cotizaciones">
            <QuoteDetailPage />
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
      // Cualquier dirección que no existe (o una entrada del menú aún sin pantalla) vuelve al inicio.
      { path: "*", element: <Navigate to="/" replace /> },
    ],
  },
]);
