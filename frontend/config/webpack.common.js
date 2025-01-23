import path from "path";
import { fileURLToPath } from "url";

import HtmlWebpackPlugin from "html-webpack-plugin";
import MiniCssExtractPlugin from "mini-css-extract-plugin";

export const rootDir = path.resolve(
  fileURLToPath(new URL(".", import.meta.url)),
  "..",
  ".."
);

const dateNow = new Date();

export const commonConfig = ({ publicPath, tsConfigFile, devMode }) => ({
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
      {
        test: /\.less$/i,
        use: [
          {
            loader: (devMode ? "style-loader" : MiniCssExtractPlugin.loader),
          },
          {
            loader: "css-loader",
          },
          {
            loader: "less-loader",
            options: {
              lessOptions: {
              noIeCompat: true,
              javascriptEnabled: true,
              }
            },
          }
        ],
      },
    ],
  },
  plugins: [
    ...(devMode ? [] : [new MiniCssExtractPlugin()]),
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
  optimization: {
    chunkIds: 'named',
    splitChunks: {
      cacheGroups: {
        styles: {
          name: (module, _chunks, cacheGroupKey) => {
            const filename = module.identifier().split('|').find((item) => (/\.less$/i).test(item));
            const modName = filename ? path.basename(filename, '.less') : cacheGroupKey;
            return `css/${cacheGroupKey}-${modName}`;
          },
          test: (m) => m.constructor.name === 'CssModule',
          chunks: 'all',
          enforce: true,
        },
      },
    },
  },
});
