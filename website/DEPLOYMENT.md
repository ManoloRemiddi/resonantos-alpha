# ResonantOS Marketing Website - Deployment Guide

## Overview

This is a static website built with Astro and Tailwind CSS v4. It's fast, responsive, and ready to deploy.

## Prerequisites

- Node.js 18+ and npm
- A Web3Forms account (free) for the waitlist form

## Quick Start

1. **Install dependencies:**
   ```bash
   npm install
   ```

2. **Set up the waitlist form:**
   - Go to https://web3forms.com and create a free account
   - Create a new form and copy your access key
   - Replace `YOUR_ACCESS_KEY_HERE` in `src/pages/index.astro` (line ~634) with your actual key
   
3. **Run development server:**
   ```bash
   npm run dev
   ```
   Open http://localhost:4321

4. **Build for production:**
   ```bash
   npm run build
   ```
   The built site will be in the `dist/` folder.

## Deployment

### Option 1: Vercel (Recommended)

1. Install Vercel CLI (optional):
   ```bash
   npm i -g vercel
   ```

2. Deploy:
   ```bash
   vercel
   ```
   
   Or connect your GitHub repo to Vercel:
   - Go to https://vercel.com/new
   - Import your repository
   - Vercel will auto-detect Astro and configure everything
   - Click Deploy

### Option 2: Netlify

1. Install Netlify CLI (optional):
   ```bash
   npm i -g netlify-cli
   ```

2. Deploy:
   ```bash
   netlify deploy --prod
   ```
   
   Or connect your GitHub repo to Netlify:
   - Go to https://app.netlify.com/start
   - Connect your repository
   - Netlify will auto-detect the build settings
   - Click Deploy

### Option 3: GitHub Pages

1. Build the site:
   ```bash
   npm run build
   ```

2. The `dist/` folder contains your static site
3. Push to a `gh-pages` branch or configure GitHub Pages to use the `dist/` folder

## Configuration

### Waitlist Form

The site uses Web3Forms (free service) for form submissions. To configure:

1. Create account at https://web3forms.com
2. Create a new form
3. Copy your access key
4. In `src/pages/index.astro`, find:
   ```html
   <input type="hidden" name="access_key" value="YOUR_ACCESS_KEY_HERE">
   ```
5. Replace `YOUR_ACCESS_KEY_HERE` with your key

### Social Links

Update these placeholder links in `src/pages/index.astro`:

- YouTube channel (search for "Subscribe →")
- Discord server (search for "Join Discord")
- Twitter/X handle (search for "@ResonantOS")
- GitHub repo (search for "GitHub (coming soon)")

### Custom Domain

#### Vercel:
1. Go to your project settings
2. Navigate to "Domains"
3. Add your custom domain (e.g., resonantos.com)
4. Update your DNS records as instructed

#### Netlify:
1. Go to "Domain settings"
2. Add custom domain
3. Configure DNS as instructed

## Performance Optimization

The site is already optimized for performance:

- **Static generation** - No server-side processing
- **Minimal JavaScript** - Only what's needed for interactivity
- **Tailwind CSS v4** - Optimized CSS with minimal overhead
- **Font preloading** - Google Fonts preconnect for faster loading
- **Semantic HTML** - Clean, accessible markup

Expected performance:
- First Contentful Paint: < 1s
- Time to Interactive: < 2s
- Lighthouse Score: 95+

## Updating Content

All content is in `src/pages/index.astro`. To update:

1. Edit the HTML/content directly
2. Run `npm run dev` to preview changes
3. Run `npm run build` to rebuild
4. Deploy the updated `dist/` folder

For more complex updates (e.g., adding pages), see [Astro documentation](https://docs.astro.build).

## Troubleshooting

### Build fails
- Make sure Node.js 18+ is installed
- Delete `node_modules` and run `npm install` again
- Check that all dependencies are installed

### Form not working
- Verify Web3Forms access key is correct
- Check browser console for errors
- Ensure form action URL is `https://api.web3forms.com/submit`

### Styles not loading
- Check that `src/styles/global.css` exists
- Verify Tailwind is properly configured in `astro.config.mjs`
- Clear browser cache and rebuild

## Project Structure

```
website/
├── src/
│   ├── pages/
│   │   └── index.astro          # Main page (all content)
│   └── styles/
│       └── global.css           # Tailwind imports
├── public/                       # Static assets (favicon, etc.)
├── astro.config.mjs             # Astro configuration
├── package.json                 # Dependencies
├── tailwind.config.mjs          # Tailwind configuration (auto-generated)
├── vercel.json                  # Vercel deployment config
└── netlify.toml                 # Netlify deployment config
```

## Tech Stack

- **Framework:** Astro 5.x (static site generator)
- **Styling:** Tailwind CSS v4
- **Fonts:** Inter (body), JetBrains Mono (monospace)
- **Form:** Web3Forms (free tier)
- **Deployment:** Vercel or Netlify (recommended)

## Support

For issues or questions:
- Check [Astro docs](https://docs.astro.build)
- Check [Tailwind docs](https://tailwindcss.com/docs)
- Check [Web3Forms docs](https://docs.web3forms.com)

---

Built with Astro 🚀
