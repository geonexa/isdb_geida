import { lazy, Suspense } from "react";
import type React from "react";
import { createBrowserRouter, Navigate, Outlet, ScrollRestoration } from "react-router-dom";

import { AuthLayout } from "@/app/layout/AuthLayout";
import { Layout } from "@/app/layout/Layout";
import Register from "@/features/auth/pages/Register";
import { ResetComplete, ResetConfirm, ResetRequest, ResetSent } from "@/features/auth/pages/PasswordReset";
import SignIn from "@/features/auth/pages/SignIn";
import Verify from "@/features/auth/pages/Verify";
import Home from "@/features/site/Home";
import ModulePage from "@/features/site/ModulePage";
import NotFound from "@/features/site/NotFound";

// /geoportal = the Data Catalog (OpenLayers: catalog, cloud-optimised layers via TiTiler, area tools,
// saved areas, toolbox). /analytics = the GIS workspace (GeoLibre).
const GisWorkspacePage = lazy(() => import("@/features/gis/GisWorkspacePage"));
const GeoPortalPage = lazy(() => import("@/features/geoportal/GeoPortalPage"));
const ProjectListPage = lazy(() => import("@/features/projects/ProjectListPage"));
const ProjectDetailPage = lazy(() => import("@/features/projects/ProjectDetailPage"));
const ProjectWizard = lazy(() => import("@/features/projects/ProjectWizard"));
const ImportPage = lazy(() => import("@/features/projects/ImportPage"));
const lazyEl = (el: React.ReactNode) => <Suspense fallback={null}>{el}</Suspense>;

function Root() {
  return (
    <>
      <ScrollRestoration />
      <Outlet />
    </>
  );
}

export const router = createBrowserRouter([
  {
    element: <Root />,
    children: [
      {
        element: <Layout />,
        children: [
          { path: "/", element: <Home /> },
          { path: "/projects/import", element: lazyEl(<ImportPage />) },
          { path: "/:slug", element: <ModulePage /> },
          { path: "*", element: <NotFound /> },
        ],
      },
      {
        element: <Layout footer={false} />,
        children: [
          { path: "/geoportal", element: <Suspense fallback={null}><GeoPortalPage /></Suspense> },
          { path: "/analytics", element: <Suspense fallback={null}><GisWorkspacePage /></Suspense> },
          // Projects: list + map, onboarding wizard, project workspace (full height).
          { path: "/projects", element: lazyEl(<ProjectListPage />) },
          { path: "/projects/review", element: lazyEl(<ProjectListPage tab="review" />) },
          { path: "/projects/new", element: lazyEl(<ProjectWizard />) },
          { path: "/projects/:code/edit", element: lazyEl(<ProjectWizard />) },
          { path: "/projects/:code", element: lazyEl(<ProjectDetailPage />) },
          // Old addresses
          { path: "/geo-portal", element: <Navigate to="/geoportal" replace /> },
          { path: "/geo-portal/classic", element: <Navigate to="/geoportal" replace /> },
        ],
      },
      {
        path: "/accounts",
        element: <AuthLayout />,
        children: [
          { path: "sign-in", element: <SignIn /> },
          { path: "register", element: <Register /> },
          { path: "verify", element: <Verify /> },
          { path: "password-reset", element: <ResetRequest /> },
          { path: "password-reset/sent", element: <ResetSent /> },
          { path: "password-reset/complete", element: <ResetComplete /> },
          { path: "password-reset/:uid/:token", element: <ResetConfirm /> },
        ],
      },
    ],
  },
]);
