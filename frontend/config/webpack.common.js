import path from "path";
import { fileURLToPath } from "url";

import HtmlWebpackPlugin from "html-webpack-plugin";

export const rootDir = path.resolve(
  fileURLToPath(new URL(".", import.meta.url)),
  "..",
  ".."
);

const dateNow = new Date();

export const commonConfig = ({ publicPath, tsConfigFile }) => ({
  devtool: "source-map",
  entry: {
    main: "./frontend/src/main",
  },
  experiments: {
    outputModule: true,
  },
  externals: {
    '@dashlive/init': 'module /libs/initialAppState.js',
    '@dashlive/options': 'module /libs/options.js',
    '@dashlive/routemap': 'module /libs/routemap.js'
  },
  output: {
    path: path.resolve(rootDir, "static", "html"),
    filename: "[name].[contenthash].js",
    clean: true,
    module: true
  },
  resolve: {
    extensions: [".ts", ".tsx", ".js"],
  },
  module: {
    rules: [
      {
        test: /\.hbs$/,
        loader: 'handlebars-loader',
        options: {
          helperDirs: [path.join(rootDir, "frontend", "html", "helpers")],
          partialDirs: [path.join(rootDir, "frontend", "html", "partials")],
        }
      },
      {
        test: /\.tsx?$/,
        use: [
          {
            loader: "ts-loader",
            options: {
              configFile: tsConfigFile,
            },
          },
        ],
      },
    ],
  },
  plugins: [
    new HtmlWebpackPlugin({
      filename: "index.html",
      template: path.join(rootDir, "frontend/html/index.hbs"),
      hash: true,
      chunks: ["main"],
      publicPath: publicPath === "" ? "/" : publicPath,
      inject: true,
      scriptLoading: "module",
      templateParameters: (_compilation, _assets, options) => ({
        htmlWebpackPlugin: {
          options,
        },
        template: {
          ...options,
          title: 'DASH live server',
          dateNow,
          publicPath,
        },
      }),
    }),
  ],
});
