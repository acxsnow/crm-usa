import { createBrowserRouter } from "react-router-dom";
import { LoginPage } from "@/features/auth/LoginPage";
import { ForgotPasswordPage } from "@/features/auth/ForgotPasswordPage";
import { ResetPasswordPage } from "@/features/auth/ResetPasswordPage";
import { AcceptInvitationPage } from "@/features/auth/AcceptInvitationPage";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { DashboardLayout } from "@/app/DashboardLayout";
import { DashboardHome } from "@/app/DashboardHome";
import { LeadsPage } from "@/features/crm/LeadsPage";
import { CustomersPage } from "@/features/crm/CustomersPage";
import { CustomerDetailPage } from "@/features/crm/CustomerDetailPage";
import { OpportunitiesPage } from "@/features/crm/OpportunitiesPage";
import { ProjectsPage } from "@/features/field-ops/ProjectsPage";
import { ProjectDetailPage } from "@/features/field-ops/ProjectDetailPage";
import { InvoicesPage } from "@/features/billing/InvoicesPage";
import { UsersPage } from "@/features/users/UsersPage";
import { AuditLogPage } from "@/features/audit/AuditLogPage";
import { CustomerSignaturePage } from "@/features/field-ops/CustomerSignaturePage";
import { ApplicationPage } from "@/features/crm/ApplicationPage";
import { ApplicationsAdminPage } from "@/features/crm/ApplicationsAdminPage";

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
      { path: "leads", element: <LeadsPage /> },
      { path: "applications/new", element: <ApplicationPage /> },
      { path: "applications", element: <ApplicationsAdminPage /> },
      { path: "customers", element: <CustomersPage /> },
      { path: "customers/:customerId", element: <CustomerDetailPage /> },
      { path: "opportunities", element: <OpportunitiesPage /> },
      { path: "projects", element: <ProjectsPage /> },
      { path: "projects/:projectId", element: <ProjectDetailPage /> },
      { path: "invoices", element: <InvoicesPage /> },
      { path: "users", element: <UsersPage /> },
      { path: "audit-log", element: <AuditLogPage /> },
    ],
  },
]);
