import path from "path";
import { fileURLToPath } from "url";
import webpack from "webpack";
import GitRevPlugin from "git-rev-webpack-plugin";

import HtmlWebpackPlugin from "html-webpack-plugin";
import MiniCssExtractPlugin from "mini-css-extract-plugin";

export const rootDir = path.resolve(
  fileURLToPath(new URL(".", import.meta.url)),
  "..",
  ".."
);

function getGitHash() {
  if (process.env.GIT_SHA) {
    return String(process.env.GIT_SHA).trim();
  }
  try {
    const gitRevPlugin = new GitRevPlugin();
    return gitRevPlugin.hash();
  } catch (err) {
    console.error(err);
    return 'n/a';
  }
}

const dateNow = new Date();

const gitHash = getGitHash();

export const commonConfig = ({ publicPath, tsConfigFile, devMode, serverPort = null }) => ({
  devtool: "source-map",
  entry: {
    main: "./frontend/src/main",
  },
  experiments: {
    outputModule: true,
  },
  externals: {
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
    new webpack.DefinePlugin({
      _GIT_HASH_: JSON.stringify(gitHash),
      _SERVER_PORT_: JSON.stringify(serverPort),
    }),
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
          gitHash,
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
