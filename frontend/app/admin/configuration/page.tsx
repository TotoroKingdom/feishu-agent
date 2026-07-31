import { notFound } from "next/navigation";
import { cookies } from "next/headers";

import {
  ConfigurationManagementPanel,
  type ConfigurationSnapshot,
  type ModelConfig,
  type PromptVersion,
  type ProjectConfig,
} from "@/components/configuration-management-panel";
import { buildAdminRequestInit } from "@/lib/admin-auth";
import { getBackendBaseUrl } from "@/lib/backend-url";

type Envelope<T> = {
  data: T;
};

async function loadJson<T>(path: string): Promise<T> {
  const cookieHeader = serializeCookies();
  const response = await fetch(
    `${getBackendBaseUrl()}${path}`,
    buildAdminRequestInit(
      {
        cache: "no-store",
      },
      { cookieHeader },
    ),
  );
  if (!response.ok) {
    throw new Error(`Failed to load ${path} (${response.status})`);
  }
  return (await response.json()) as T;
}

function serializeCookies(): string {
  return cookies()
    .getAll()
    .map(({ name, value }) => `${name}=${value}`)
    .join("; ");
}

async function loadConfigurationSnapshot(): Promise<ConfigurationSnapshot> {
  const [project, repositories, feishuResources, modelConfig, prompts] = await Promise.all([
    loadJson<Envelope<ProjectConfig>>("/api/v1/admin/project"),
    loadJson<Envelope<ConfigurationSnapshot["repositories"]>>("/api/v1/admin/project/repositories"),
    loadJson<Envelope<ConfigurationSnapshot["feishuResources"]>>("/api/v1/admin/project/feishu-resources"),
    loadJson<Envelope<ModelConfig>>("/api/v1/admin/model-config"),
    loadJson<Envelope<PromptVersion[]>>("/api/v1/admin/prompts?type=report"),
  ]);

  return {
    project: project.data,
    repositories: repositories.data,
    feishuResources: feishuResources.data,
    modelConfig: modelConfig.data,
    prompts: prompts.data,
  };
}

export default async function ConfigurationPage() {
  try {
    const snapshot = await loadConfigurationSnapshot();
    return <ConfigurationManagementPanel initialState={snapshot} />;
  } catch (error) {
    if (error instanceof Error && error.message.includes("(404)")) {
      notFound();
    }

    const message = error instanceof Error ? error.message : "Unable to load configuration";
    return (
      <main className="app-shell">
        <div className="page">
          <section className="panel">
            <p className="kicker">Admin Configuration</p>
            <h1 className="title">Failed to load</h1>
            <p className="lede">{message}</p>
          </section>
        </div>
      </main>
    );
  }
}
