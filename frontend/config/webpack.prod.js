import path from "path";
import { commonConfig, rootDir } from "./webpack.common.js";

/*   tsConfigFile: path.resolve(rootDir, "config", "tsconfig.prod.json"), */

const common = commonConfig({
  publicPath: '/static/html',
  tsConfigFile: path.resolve(rootDir, "tsconfig.json"),
  devMode: false,
});

export default {
  ...common,
  mode: "production",
};
