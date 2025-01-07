import path from "path";
import { rootDir, commonConfig } from "./frontend/config/webpack.common.js";

const apiTokens = {
  csrfTokens: {
      files: null,
      kids: null,
      streams: null,
      upload: null
  },
  accessToken: null,
  refreshToken: null,
};

const initialUserState = {
  isAuthenticated: false,
  groups:[],
};

const serverPort = process.env.SERVER_PORT || '5000';

const common = commonConfig({
  publicPath: "",
  template: path.join(rootDir, "frontend/html/index.hbs"),
  tsConfigFile: "tsconfig.json",
  initialTokens: JSON.stringify(apiTokens),
  initialUser: JSON.stringify(initialUserState),
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
          '/libs',
        ],
        target: `http://localhost:${serverPort}/`,
      },
    ],
  },
};
