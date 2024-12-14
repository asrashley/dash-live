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
                branches: 75,
                functions: 75,
                lines: 70,
                statements: 70
            }
        },
	},
	resolve: {
		alias: [
			{
				find: "/libs/content_roles.js",
				replacement: resolve(projectRootDir, 'static/js/mocks/content_roles.js')
			},
			{
				find: '/libs/routemap.js',
				replacement: resolve(projectRootDir, 'static/js/mocks/routemap.js')
			},
			{
				find: '/libs/options.js',
				replacement: resolve(projectRootDir, 'static/js/mocks/options.js')
			},
			{
				find: '@dashlive/hooks',
				replacement: resolve(projectRootDir, 'static/js/spa/hooks/index.js')
			},
			{
				find: '@dashlive/ui',
				replacement: resolve(projectRootDir, 'static/js/spa/components/index.js')
			}
		]
	}
})