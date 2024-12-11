import { resolve } from 'path';
import { defineConfig } from 'vitest/config';

const projectRootDir = resolve(__dirname);

export default defineConfig({
	test: {
		environment: 'jsdom',
        setupFiles: './static/js/test/setup.js',
        coverage: {
            include: [
                "static/js/spa/**/*.js",
            ],
            exclude: [
                "static/js/test/*.js",
                "static/js/spa/**/*.test.js",
            ],
            thresholds: {
                branches: 65,
                functions: 30,
                lines: 15,
                statements: 15
            }
        },
	},
	resolve: {
		alias: [
			{
				find: '/libs/routemap.js',
				replacement: resolve(projectRootDir, 'static/js/mocks/routemap.js')
			},
			{
				find: '@dashlive/hooks',
				replacement: resolve(projectRootDir, 'static/js/spa/hooks/index.js')
			}
		]
	}
})