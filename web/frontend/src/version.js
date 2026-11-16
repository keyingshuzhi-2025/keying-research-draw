import packageMetadata from "../package.json";

const normalizedVersion = String(packageMetadata.version || "0.0.0").replace(/^[vV]/, "");

export const APP_VERSION = `v${normalizedVersion}`;
