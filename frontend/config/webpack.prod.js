import path from "path";
import { commonConfig, rootDir } from "./webpack.common.js";

const publicPath = "{{ publicPath }}";

const common = commonConfig({
  publicPath,
  template: "frontend/html/prod.ejs",
  tsConfigFile: path.resolve(rootDir, "config/tsconfig.prod.json"),
});

export default {
  ...common,
  mode: "production",
};
