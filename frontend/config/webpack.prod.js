import path from "path";
import { commonConfig, rootDir } from "./webpack.common.js";

const common = commonConfig({
  publicPath: '/static/html',
  tsConfigFile: path.resolve(rootDir, "tsconfig.prod.json"),
  devMode: false,
});

export default {
  ...common,
  mode: "production",
};
