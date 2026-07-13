import { useState } from "react";
import { useMigrationStore } from "./store/useMigrationStore";
import { ProjectListPage } from "./components/pages/ProjectListPage/ProjectListPage";
import { ProjectPage } from "./components/pages/ProjectPage/ProjectPage";
import { ServicesProvider, type Services } from "./services/ServicesContext";
import {
  BackendHttpAdapter,
  CMSInjectionAdapter,
  ChromeStorageCredentialAdapter,
  DOMExtractorAdapter,
  LabelAdapter,
  PageAdapter,
  WSClientAdapter,
} from "./services/adapters";

/**
 * Build the service bundle once at app startup. Stateless adapters become
 * singletons; the per-operation WSClient is exposed as a factory so each
 * migration run gets a fresh connection lifecycle.
 */
function makeServices(): Services {
  return {
    backendPort: new BackendHttpAdapter(),
    cmsPort: new CMSInjectionAdapter(),
    credentialPort: new ChromeStorageCredentialAdapter(),
    extractorPort: new DOMExtractorAdapter(),
    labelPort: new LabelAdapter(),
    pagePort: new PageAdapter(),
    createWSClient: () => new WSClientAdapter(),
  };
}

export default function App() {
  const view = useMigrationStore((state) => state.view);
  // Lazy useState init so adapter constructors run exactly once per app load,
  // not on every render.
  const [services] = useState(makeServices);

  return (
    <ServicesProvider services={services}>
      {view === "project" ? <ProjectPage /> : <ProjectListPage />}
    </ServicesProvider>
  );
}
