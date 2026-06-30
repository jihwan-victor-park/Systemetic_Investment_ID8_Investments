// @ts-check
const { themes } = require('prism-react-renderer');

/** @type {import('@docusaurus/types').Config} */
const config = {
  title: 'ID8 AI Intelligence',
  tagline: 'Ambitious ideas, made legible.',
  favicon: 'img/logo_charcoal.png',

  url: 'https://ocachin.github.io',
  baseUrl: '/id8-intelligence/',
  organizationName: 'ocachin',
  projectName: 'id8-intelligence',
  onBrokenLinks: 'warn',
  onBrokenMarkdownLinks: 'warn',

  i18n: { defaultLocale: 'en', locales: ['en'] },

  presets: [
    [
      'classic',
      /** @type {import('@docusaurus/preset-classic').Options} */
      ({
        docs: {
          routeBasePath: 'docs',
          sidebarPath: require.resolve('./sidebars.js'),
        },
        blog: false,
        theme: { customCss: require.resolve('./src/css/custom.css') },
      }),
    ],
  ],

  themeConfig:
    /** @type {import('@docusaurus/preset-classic').ThemeConfig} */
    ({
      colorMode: { defaultMode: 'light', respectPrefersColorScheme: true },
      navbar: {
        logo: {
          alt: 'ID8 Investments',
          src: 'img/logo_charcoal.png',
          srcDark: 'img/logo_white.png',
          height: '15px',
        },
        items: [
          { to: '/docs/overview', label: 'AI Capabilities', position: 'left', className: 'nav-internal' },
          { to: '/docs/projects/pitchbook-attio', label: 'Systems', position: 'left', className: 'nav-internal' },
          { to: '/docs/research', label: 'Research', position: 'left', className: 'nav-internal' },
          { to: '/docs/admin', label: 'Admin', position: 'left', className: 'nav-internal' },
          { to: '/investors', label: 'Investor View', position: 'right' },
        ],
      },
      footer: {
        style: 'light',
        copyright: 'ID8 Investments  |  Confidential  |  Internal use only',
      },
      prism: { theme: themes.github, darkTheme: themes.dracula },
    }),
};

module.exports = config;
