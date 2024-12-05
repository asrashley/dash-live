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
            ],
            thresholds: {
                branches: 75,
                functions: 80,
                lines: 75,
                statements: 75
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