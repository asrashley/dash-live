import path from "path";
import { rootDir, commonConfig } from "./frontend/config/webpack.common.js";

const serverPort = process.env.SERVER_PORT || '5000';

const common = commonConfig({
  publicPath: "",
  tsConfigFile: "tsconfig.json",
  devMode: true,
  serverPort,
});

export default {
  ...common,
  mode: "development",
  devtool: "inline-source-map",
  devServer: {
    historyApiFallback: true,
    hot: false,
    host: "0.0.0.0",
    allowedHosts: "all",
    static: [
      {
        directory: path.join(rootDir, "static"),
        publicPath: "/static",
      },
    ],
    proxy: [
      {
        context: [
          '/api',
          '/clearkey',
          '/dash',
          '/es5',
          '/libs',
          '/media/inspect',
          '/mps',
          '/streams',
        ],
        target: `http://localhost:${serverPort}/`,
      },
    ],
  },
};
