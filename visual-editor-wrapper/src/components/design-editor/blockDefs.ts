export interface BlockDef {
  id: string;
  label: string;
  category: 'Layout' | 'Nav' | 'Hero' | 'Cards' | 'Forms' | 'Footer' | 'Typography' | 'Interactive' | 'Media';
  content: string;
  media: string;
}

const S = 'rgba(255,255,255,0.15)';   // stroke
const F = 'rgba(255,255,255,0.05)';   // fill
const G = '#2db370';                   // green accent

export const BLOCKS: BlockDef[] = [
  // ── Layout ──────────────────────────────────────────────────────────────
  {
    id: 'app-section',
    label: 'Section',
    category: 'Layout',
    media: `<svg viewBox="0 0 80 60" xmlns="http://www.w3.org/2000/svg"><rect width="80" height="60" fill="${F}"/><rect x="4" y="8" width="72" height="44" rx="2" fill="none" stroke="${S}" stroke-width="1"/><line x1="4" y1="20" x2="76" y2="20" stroke="${S}" stroke-width="0.5"/></svg>`,
    content: `<section class="py-16 px-6"><div class="max-w-5xl mx-auto"><p class="text-gray-400 text-sm">Section content</p></div></section>`,
  },
  {
    id: 'app-two-col',
    label: 'Two Column',
    category: 'Layout',
    media: `<svg viewBox="0 0 80 60" xmlns="http://www.w3.org/2000/svg"><rect width="80" height="60" fill="${F}"/><rect x="4" y="8" width="34" height="44" rx="2" fill="none" stroke="${S}" stroke-width="1"/><rect x="42" y="8" width="34" height="44" rx="2" fill="none" stroke="${S}" stroke-width="1"/></svg>`,
    content: `<div class="grid grid-cols-2 gap-8 px-6 py-12"><div class="space-y-4"><h2 class="text-2xl font-bold">Left Column</h2><p class="text-gray-400">Content here</p></div><div class="space-y-4"><h2 class="text-2xl font-bold">Right Column</h2><p class="text-gray-400">Content here</p></div></div>`,
  },
  {
    id: 'app-three-col',
    label: 'Three Column',
    category: 'Layout',
    media: `<svg viewBox="0 0 80 60" xmlns="http://www.w3.org/2000/svg"><rect width="80" height="60" fill="${F}"/><rect x="3" y="8" width="22" height="44" rx="2" fill="none" stroke="${S}" stroke-width="1"/><rect x="29" y="8" width="22" height="44" rx="2" fill="none" stroke="${S}" stroke-width="1"/><rect x="55" y="8" width="22" height="44" rx="2" fill="none" stroke="${S}" stroke-width="1"/></svg>`,
    content: `<div class="grid grid-cols-3 gap-6 px-6 py-12"><div><h3 class="font-semibold mb-2">Column 1</h3><p class="text-sm text-gray-400">Content</p></div><div><h3 class="font-semibold mb-2">Column 2</h3><p class="text-sm text-gray-400">Content</p></div><div><h3 class="font-semibold mb-2">Column 3</h3><p class="text-sm text-gray-400">Content</p></div></div>`,
  },
  {
    id: 'app-container',
    label: 'Container',
    category: 'Layout',
    media: `<svg viewBox="0 0 80 60" xmlns="http://www.w3.org/2000/svg"><rect width="80" height="60" fill="${F}"/><rect x="4" y="8" width="72" height="44" rx="2" fill="none" stroke="${S}" stroke-width="1"/><rect x="12" y="16" width="56" height="28" rx="1" fill="none" stroke="${S}" stroke-dasharray="2 2" stroke-width="0.8"/></svg>`,
    content: `<div class="max-w-5xl mx-auto px-6 py-12"><p class="text-gray-400 text-sm">Container content</p></div>`,
  },

  // ── Nav ──────────────────────────────────────────────────────────────────
  {
    id: 'app-navbar',
    label: 'Top Navbar',
    category: 'Nav',
    media: `<svg viewBox="0 0 80 60" xmlns="http://www.w3.org/2000/svg"><rect width="80" height="60" fill="${F}"/><rect x="0" y="4" width="80" height="14" fill="rgba(255,255,255,0.06)" stroke="${S}" stroke-width="0.5"/><rect x="6" y="8" width="14" height="6" rx="1" fill="${G}" opacity="0.7"/><rect x="44" y="9" width="8" height="3" rx="0.5" fill="${S}"/><rect x="54" y="9" width="8" height="3" rx="0.5" fill="${S}"/><rect x="65" y="8" width="10" height="5" rx="1" fill="${G}" opacity="0.5"/></svg>`,
    content: `<nav class="flex items-center justify-between px-6 py-4 border-b border-gray-800 bg-gray-900"><span class="text-lg font-bold text-white">Logo</span><div class="flex items-center gap-6"><a href="#" class="text-sm text-gray-400 hover:text-white">Home</a><a href="#" class="text-sm text-gray-400 hover:text-white">About</a><a href="#" class="text-sm text-gray-400 hover:text-white">Pricing</a><a href="#" class="px-4 py-2 rounded-lg bg-green-600 text-white text-sm font-medium">Sign up</a></div></nav>`,
  },
  {
    id: 'app-sidebar-nav',
    label: 'Sidebar Nav',
    category: 'Nav',
    media: `<svg viewBox="0 0 80 60" xmlns="http://www.w3.org/2000/svg"><rect width="80" height="60" fill="${F}"/><rect x="0" y="0" width="22" height="60" fill="rgba(255,255,255,0.04)" stroke="${S}" stroke-width="0.5"/><rect x="6" y="8" width="10" height="4" rx="0.5" fill="${G}" opacity="0.6"/><rect x="4" y="18" width="14" height="3" rx="0.5" fill="${S}"/><rect x="4" y="24" width="14" height="3" rx="0.5" fill="${S}"/><rect x="4" y="30" width="14" height="3" rx="0.5" fill="${S}"/><rect x="4" y="36" width="10" height="3" rx="0.5" fill="${S}"/></svg>`,
    content: `<div class="flex h-64"><aside class="w-48 bg-gray-900 border-r border-gray-800 p-4 flex flex-col gap-1"><div class="text-lg font-bold text-white mb-4">App</div><a href="#" class="px-3 py-2 rounded-lg text-sm text-green-400 bg-green-900/30">Dashboard</a><a href="#" class="px-3 py-2 rounded-lg text-sm text-gray-400 hover:bg-gray-800">Users</a><a href="#" class="px-3 py-2 rounded-lg text-sm text-gray-400 hover:bg-gray-800">Settings</a></aside><main class="flex-1 p-6 bg-gray-950"><p class="text-gray-400 text-sm">Main content area</p></main></div>`,
  },

  // ── Hero ─────────────────────────────────────────────────────────────────
  {
    id: 'app-hero-centered',
    label: 'Centered Hero',
    category: 'Hero',
    media: `<svg viewBox="0 0 80 60" xmlns="http://www.w3.org/2000/svg"><rect width="80" height="60" fill="${F}"/><rect x="12" y="10" width="56" height="6" rx="1" fill="${S}"/><rect x="18" y="20" width="44" height="3" rx="1" fill="rgba(255,255,255,0.08)"/><rect x="22" y="25" width="36" height="3" rx="1" fill="rgba(255,255,255,0.08)"/><rect x="22" y="34" width="16" height="7" rx="1" fill="${G}" opacity="0.8"/><rect x="42" y="34" width="16" height="7" rx="1" fill="none" stroke="${S}" stroke-width="0.8"/></svg>`,
    content: `<section class="py-24 px-6 text-center bg-gray-950"><div class="max-w-3xl mx-auto"><h1 class="text-5xl font-extrabold text-white tracking-tight mb-6">Build Something Amazing</h1><p class="text-xl text-gray-400 mb-10">A compelling description of your product and the value it delivers to users.</p><div class="flex items-center justify-center gap-4"><a href="#" class="px-8 py-3 rounded-lg bg-green-600 text-white font-semibold hover:bg-green-500">Get started</a><a href="#" class="px-8 py-3 rounded-lg border border-gray-700 text-gray-300 font-semibold hover:border-gray-500">Learn more</a></div></div></section>`,
  },
  {
    id: 'app-hero-split',
    label: 'Split Hero',
    category: 'Hero',
    media: `<svg viewBox="0 0 80 60" xmlns="http://www.w3.org/2000/svg"><rect width="80" height="60" fill="${F}"/><rect x="4" y="8" width="36" height="6" rx="1" fill="${S}"/><rect x="4" y="18" width="30" height="2.5" rx="1" fill="rgba(255,255,255,0.08)"/><rect x="4" y="23" width="26" height="2.5" rx="1" fill="rgba(255,255,255,0.08)"/><rect x="4" y="32" width="16" height="6" rx="1" fill="${G}" opacity="0.8"/><rect x="44" y="8" width="32" height="44" rx="2" fill="rgba(255,255,255,0.06)" stroke="${S}" stroke-width="0.8"/><line x1="52" y1="20" x2="68" y2="20" stroke="${S}" stroke-width="0.5"/><line x1="52" y1="26" x2="68" y2="26" stroke="${S}" stroke-width="0.5"/></svg>`,
    content: `<section class="py-20 px-6 bg-gray-950"><div class="max-w-6xl mx-auto grid grid-cols-2 gap-12 items-center"><div><h1 class="text-4xl font-extrabold text-white mb-6 leading-tight">Your Product<br/>Headline Here</h1><p class="text-gray-400 text-lg mb-8">Describe what makes your product unique and why users should choose it.</p><a href="#" class="inline-block px-8 py-3 rounded-lg bg-green-600 text-white font-semibold">Start free trial</a></div><div class="bg-gray-800 rounded-2xl aspect-video flex items-center justify-center"><span class="text-gray-500 text-sm">Product screenshot</span></div></div></section>`,
  },

  // ── Cards ─────────────────────────────────────────────────────────────────
  {
    id: 'app-feature-card',
    label: 'Feature Card',
    category: 'Cards',
    media: `<svg viewBox="0 0 80 60" xmlns="http://www.w3.org/2000/svg"><rect width="80" height="60" fill="${F}"/><rect x="4" y="4" width="23" height="32" rx="2" fill="rgba(255,255,255,0.04)" stroke="${S}" stroke-width="0.8"/><rect x="8" y="9" width="8" height="8" rx="1" fill="${G}" opacity="0.5"/><rect x="8" y="20" width="14" height="2.5" rx="0.5" fill="${S}"/><rect x="8" y="25" width="12" height="2" rx="0.5" fill="rgba(255,255,255,0.07)"/><rect x="30" y="4" width="23" height="32" rx="2" fill="rgba(255,255,255,0.04)" stroke="${S}" stroke-width="0.8"/><rect x="34" y="9" width="8" height="8" rx="1" fill="${G}" opacity="0.5"/><rect x="34" y="20" width="14" height="2.5" rx="0.5" fill="${S}"/><rect x="56" y="4" width="20" height="32" rx="2" fill="rgba(255,255,255,0.04)" stroke="${S}" stroke-width="0.8"/></svg>`,
    content: `<div class="grid grid-cols-3 gap-6 px-6 py-12 bg-gray-950">${['Fast', 'Secure', 'Scalable'].map(f => `<div class="p-6 rounded-2xl border border-gray-800 bg-gray-900"><div class="w-10 h-10 rounded-xl bg-green-900/40 flex items-center justify-center mb-4"><svg class="w-5 h-5 text-green-400" fill="currentColor" viewBox="0 0 20 20"><path d="M10 2L2 7l8 5 8-5-8-5zM2 13l8 5 8-5"/></svg></div><h3 class="text-white font-semibold mb-2">${f}</h3><p class="text-gray-400 text-sm">Description of this feature and how it benefits your users.</p></div>`).join('')}</div>`,
  },
  {
    id: 'app-pricing-card',
    label: 'Pricing Card',
    category: 'Cards',
    media: `<svg viewBox="0 0 80 60" xmlns="http://www.w3.org/2000/svg"><rect width="80" height="60" fill="${F}"/><rect x="10" y="4" width="60" height="52" rx="3" fill="rgba(255,255,255,0.04)" stroke="${S}" stroke-width="0.8"/><rect x="18" y="10" width="24" height="4" rx="1" fill="${S}"/><rect x="18" y="18" width="14" height="8" rx="1" fill="${G}" opacity="0.6"/><rect x="14" y="30" width="52" height="1.5" stroke="${S}" stroke-width="0.5"/><rect x="18" y="35" width="30" height="2" rx="0.5" fill="rgba(255,255,255,0.07)"/><rect x="18" y="40" width="26" height="2" rx="0.5" fill="rgba(255,255,255,0.07)"/><rect x="18" y="48" width="44" height="5" rx="1" fill="${G}" opacity="0.7"/></svg>`,
    content: `<div class="max-w-sm mx-auto p-8 rounded-2xl border border-gray-700 bg-gray-900 my-8"><h3 class="text-white font-semibold text-lg mb-1">Pro</h3><p class="text-gray-400 text-sm mb-6">For growing teams</p><div class="text-4xl font-bold text-white mb-6">$49<span class="text-lg font-normal text-gray-400">/mo</span></div><ul class="space-y-3 mb-8">${['Unlimited projects','Priority support','Custom domain','Analytics'].map(f=>`<li class="flex items-center gap-2 text-sm text-gray-300"><span class="text-green-400">✓</span>${f}</li>`).join('')}</ul><a href="#" class="block w-full text-center py-3 rounded-lg bg-green-600 text-white font-semibold">Get started</a></div>`,
  },
  {
    id: 'app-testimonial',
    label: 'Testimonial',
    category: 'Cards',
    media: `<svg viewBox="0 0 80 60" xmlns="http://www.w3.org/2000/svg"><rect width="80" height="60" fill="${F}"/><rect x="8" y="8" width="64" height="44" rx="3" fill="rgba(255,255,255,0.04)" stroke="${S}" stroke-width="0.8"/><rect x="16" y="16" width="48" height="2" rx="0.5" fill="rgba(255,255,255,0.07)"/><rect x="16" y="21" width="40" height="2" rx="0.5" fill="rgba(255,255,255,0.07)"/><rect x="16" y="26" width="44" height="2" rx="0.5" fill="rgba(255,255,255,0.07)"/><circle cx="22" cy="40" r="6" fill="${G}" opacity="0.4"/><rect x="32" y="37" width="20" height="2.5" rx="0.5" fill="${S}"/><rect x="32" y="42" width="14" height="2" rx="0.5" fill="rgba(255,255,255,0.07)"/></svg>`,
    content: `<div class="max-w-2xl mx-auto px-8 py-12 rounded-2xl border border-gray-800 bg-gray-900 my-8"><blockquote class="text-xl text-white font-medium leading-relaxed mb-8">"This product completely transformed how our team works. I can't imagine going back."</blockquote><div class="flex items-center gap-4"><div class="w-12 h-12 rounded-full bg-green-800/50 flex items-center justify-center text-green-400 font-bold">JD</div><div><p class="text-white font-semibold text-sm">Jane Doe</p><p class="text-gray-400 text-sm">CEO, Acme Corp</p></div></div></div>`,
  },

  // ── Forms ─────────────────────────────────────────────────────────────────
  {
    id: 'app-contact-form',
    label: 'Contact Form',
    category: 'Forms',
    media: `<svg viewBox="0 0 80 60" xmlns="http://www.w3.org/2000/svg"><rect width="80" height="60" fill="${F}"/><rect x="8" y="6" width="64" height="48" rx="2" fill="rgba(255,255,255,0.04)" stroke="${S}" stroke-width="0.8"/><rect x="14" y="13" width="52" height="6" rx="1" fill="${S}" opacity="0.4"/><rect x="14" y="22" width="52" height="6" rx="1" fill="${S}" opacity="0.4"/><rect x="14" y="31" width="52" height="12" rx="1" fill="${S}" opacity="0.4"/><rect x="14" y="46" width="24" height="5" rx="1" fill="${G}" opacity="0.7"/></svg>`,
    content: `<div class="max-w-lg mx-auto p-8 rounded-2xl border border-gray-800 bg-gray-900 my-8"><h2 class="text-2xl font-bold text-white mb-6">Get in touch</h2><div class="space-y-4"><div><label class="block text-sm text-gray-400 mb-1">Name</label><input type="text" placeholder="Your name" class="w-full px-4 py-2.5 rounded-lg border border-gray-700 bg-gray-950 text-white text-sm"/></div><div><label class="block text-sm text-gray-400 mb-1">Email</label><input type="email" placeholder="you@example.com" class="w-full px-4 py-2.5 rounded-lg border border-gray-700 bg-gray-950 text-white text-sm"/></div><div><label class="block text-sm text-gray-400 mb-1">Message</label><textarea rows="4" placeholder="Your message..." class="w-full px-4 py-2.5 rounded-lg border border-gray-700 bg-gray-950 text-white text-sm resize-none"></textarea></div><button class="px-6 py-3 rounded-lg bg-green-600 text-white font-semibold text-sm">Send message</button></div></div>`,
  },
  {
    id: 'app-login-form',
    label: 'Login Form',
    category: 'Forms',
    media: `<svg viewBox="0 0 80 60" xmlns="http://www.w3.org/2000/svg"><rect width="80" height="60" fill="${F}"/><rect x="14" y="4" width="52" height="52" rx="3" fill="rgba(255,255,255,0.04)" stroke="${S}" stroke-width="0.8"/><rect x="24" y="12" width="32" height="4" rx="1" fill="${S}"/><rect x="20" y="22" width="40" height="6" rx="1" fill="${S}" opacity="0.4"/><rect x="20" y="32" width="40" height="6" rx="1" fill="${S}" opacity="0.4"/><rect x="20" y="42" width="40" height="6" rx="1" fill="${G}" opacity="0.7"/></svg>`,
    content: `<div class="max-w-md mx-auto p-8 rounded-2xl border border-gray-800 bg-gray-900 my-8"><h2 class="text-2xl font-bold text-white text-center mb-8">Welcome back</h2><div class="space-y-4"><div><label class="block text-sm text-gray-400 mb-1">Email</label><input type="email" placeholder="you@example.com" class="w-full px-4 py-2.5 rounded-lg border border-gray-700 bg-gray-950 text-white text-sm"/></div><div><label class="block text-sm text-gray-400 mb-1">Password</label><input type="password" placeholder="••••••••" class="w-full px-4 py-2.5 rounded-lg border border-gray-700 bg-gray-950 text-white text-sm"/></div><button class="w-full py-3 rounded-lg bg-green-600 text-white font-semibold">Sign in</button><p class="text-center text-sm text-gray-400">Don't have an account? <a href="#" class="text-green-400">Sign up</a></p></div></div>`,
  },
  {
    id: 'app-newsletter',
    label: 'Newsletter',
    category: 'Forms',
    media: `<svg viewBox="0 0 80 60" xmlns="http://www.w3.org/2000/svg"><rect width="80" height="60" fill="${F}"/><rect x="8" y="14" width="64" height="32" rx="2" fill="rgba(255,255,255,0.04)" stroke="${S}" stroke-width="0.8"/><rect x="16" y="20" width="48" height="4" rx="1" fill="${S}"/><rect x="20" y="28" width="24" height="5" rx="1" fill="${S}" opacity="0.4"/><rect x="46" y="28" width="18" height="5" rx="1" fill="${G}" opacity="0.7"/><rect x="16" y="37" width="30" height="2.5" rx="0.5" fill="rgba(255,255,255,0.06)"/></svg>`,
    content: `<section class="py-16 px-6 text-center bg-gray-950 border-t border-gray-800"><h2 class="text-3xl font-bold text-white mb-3">Stay in the loop</h2><p class="text-gray-400 mb-8">Get product updates and news delivered to your inbox.</p><div class="flex items-center max-w-md mx-auto gap-3"><input type="email" placeholder="you@example.com" class="flex-1 px-4 py-3 rounded-lg border border-gray-700 bg-gray-900 text-white text-sm"/><button class="px-6 py-3 rounded-lg bg-green-600 text-white font-semibold whitespace-nowrap">Subscribe</button></div></section>`,
  },

  // ── Footer ────────────────────────────────────────────────────────────────
  {
    id: 'app-footer-simple',
    label: 'Simple Footer',
    category: 'Footer',
    media: `<svg viewBox="0 0 80 60" xmlns="http://www.w3.org/2000/svg"><rect width="80" height="60" fill="${F}"/><rect x="0" y="40" width="80" height="20" fill="rgba(255,255,255,0.04)" stroke="${S}" stroke-width="0.5"/><rect x="6" y="47" width="16" height="3" rx="0.5" fill="${G}" opacity="0.5"/><rect x="30" y="47" width="8" height="3" rx="0.5" fill="${S}"/><rect x="40" y="47" width="8" height="3" rx="0.5" fill="${S}"/><rect x="50" y="47" width="8" height="3" rx="0.5" fill="${S}"/></svg>`,
    content: `<footer class="border-t border-gray-800 bg-gray-950 px-6 py-8"><div class="max-w-6xl mx-auto flex items-center justify-between"><span class="text-white font-bold">Logo</span><nav class="flex items-center gap-6"><a href="#" class="text-sm text-gray-400 hover:text-white">Privacy</a><a href="#" class="text-sm text-gray-400 hover:text-white">Terms</a><a href="#" class="text-sm text-gray-400 hover:text-white">Contact</a></nav><p class="text-sm text-gray-500">© 2026 Company</p></div></footer>`,
  },
  {
    id: 'app-footer-multi',
    label: 'Multi-column Footer',
    category: 'Footer',
    media: `<svg viewBox="0 0 80 60" xmlns="http://www.w3.org/2000/svg"><rect width="80" height="60" fill="${F}"/><rect x="0" y="10" width="80" height="50" fill="rgba(255,255,255,0.04)" stroke="${S}" stroke-width="0.5"/><rect x="6" y="16" width="12" height="3" rx="0.5" fill="${G}" opacity="0.5"/><rect x="6" y="23" width="10" height="2" rx="0.5" fill="${S}"/><rect x="6" y="27" width="10" height="2" rx="0.5" fill="${S}"/><rect x="24" y="16" width="10" height="3" rx="0.5" fill="${S}"/><rect x="24" y="23" width="8" height="2" rx="0.5" fill="rgba(255,255,255,0.07)"/><rect x="24" y="27" width="8" height="2" rx="0.5" fill="rgba(255,255,255,0.07)"/><rect x="42" y="16" width="10" height="3" rx="0.5" fill="${S}"/><rect x="42" y="23" width="8" height="2" rx="0.5" fill="rgba(255,255,255,0.07)"/><rect x="60" y="16" width="14" height="3" rx="0.5" fill="${S}"/><rect x="60" y="23" width="12" height="2" rx="0.5" fill="rgba(255,255,255,0.07)"/><rect x="0" y="44" width="80" height="0.5" fill="${S}"/><rect x="6" y="48" width="24" height="2" rx="0.5" fill="rgba(255,255,255,0.07)"/></svg>`,
    content: `<footer class="border-t border-gray-800 bg-gray-950 px-6 py-12"><div class="max-w-6xl mx-auto grid grid-cols-4 gap-8 mb-12"><div><span class="text-white font-bold text-lg">Logo</span><p class="text-gray-400 text-sm mt-3">Building great products for teams worldwide.</p></div>${['Product','Company','Resources'].map(c=>`<div><h4 class="text-white font-semibold text-sm mb-4">${c}</h4><ul class="space-y-2">${['Features','Pricing','Docs'].map(l=>`<li><a href="#" class="text-gray-400 text-sm hover:text-white">${l}</a></li>`).join('')}</ul></div>`).join('')}</div><div class="border-t border-gray-800 pt-6 flex items-center justify-between"><p class="text-gray-500 text-sm">© 2026 Company Inc.</p><div class="flex gap-4"><a href="#" class="text-gray-400 text-sm hover:text-white">Privacy</a><a href="#" class="text-gray-400 text-sm hover:text-white">Terms</a></div></div></div></footer>`,
  },

  // ── Typography ────────────────────────────────────────────────────────────
  {
    id: 'app-heading',
    label: 'Heading',
    category: 'Typography',
    media: `<svg viewBox="0 0 80 60" xmlns="http://www.w3.org/2000/svg"><rect width="80" height="60" fill="${F}"/><rect x="6" y="18" width="68" height="10" rx="2" fill="${S}"/><rect x="6" y="34" width="50" height="5" rx="1" fill="rgba(255,255,255,0.07)"/></svg>`,
    content: `<h1 class="text-4xl font-extrabold text-gray-900 tracking-tight leading-tight mb-4">Your Heading Here</h1>`,
  },
  {
    id: 'app-paragraph',
    label: 'Paragraph',
    category: 'Typography',
    media: `<svg viewBox="0 0 80 60" xmlns="http://www.w3.org/2000/svg"><rect width="80" height="60" fill="${F}"/><rect x="6" y="14" width="68" height="3" rx="1" fill="${S}"/><rect x="6" y="21" width="64" height="3" rx="1" fill="${S}"/><rect x="6" y="28" width="68" height="3" rx="1" fill="${S}"/><rect x="6" y="35" width="42" height="3" rx="1" fill="${S}"/></svg>`,
    content: `<p class="text-base text-gray-600 leading-relaxed mb-4">Write your paragraph text here. Double-click to start editing this block directly inside the canvas.</p>`,
  },
  {
    id: 'app-blockquote',
    label: 'Blockquote',
    category: 'Typography',
    media: `<svg viewBox="0 0 80 60" xmlns="http://www.w3.org/2000/svg"><rect width="80" height="60" fill="${F}"/><rect x="6" y="12" width="3" height="36" rx="1" fill="${G}"/><rect x="14" y="18" width="56" height="3" rx="1" fill="${S}"/><rect x="14" y="25" width="50" height="3" rx="1" fill="${S}"/><rect x="14" y="32" width="40" height="3" rx="1" fill="${S}"/></svg>`,
    content: `<blockquote class="border-l-4 border-green-600 pl-6 py-2 my-6"><p class="text-xl text-gray-700 italic leading-relaxed">"This is a blockquote. Replace this text with a meaningful quote or callout."</p><cite class="block mt-3 text-sm text-gray-500 not-italic">— Author Name</cite></blockquote>`,
  },
  {
    id: 'app-badge',
    label: 'Badge',
    category: 'Typography',
    media: `<svg viewBox="0 0 80 60" xmlns="http://www.w3.org/2000/svg"><rect width="80" height="60" fill="${F}"/><rect x="22" y="22" width="36" height="16" rx="8" fill="${G}" opacity="0.5"/><rect x="28" y="27" width="24" height="5" rx="1" fill="rgba(255,255,255,0.6)"/></svg>`,
    content: `<span class="inline-block px-3 py-1 rounded-full text-xs font-semibold bg-green-100 text-green-700">New feature</span>`,
  },

  // ── Interactive ───────────────────────────────────────────────────────────
  {
    id: 'app-button-primary',
    label: 'Button Primary',
    category: 'Interactive',
    media: `<svg viewBox="0 0 80 60" xmlns="http://www.w3.org/2000/svg"><rect width="80" height="60" fill="${F}"/><rect x="16" y="20" width="48" height="20" rx="4" fill="${G}" opacity="0.8"/><rect x="24" y="27" width="32" height="6" rx="1" fill="rgba(255,255,255,0.7)"/></svg>`,
    content: `<button class="px-6 py-3 rounded-lg bg-green-600 text-white font-semibold text-sm hover:bg-green-500 transition-colors">Click me</button>`,
  },
  {
    id: 'app-button-outline',
    label: 'Button Outline',
    category: 'Interactive',
    media: `<svg viewBox="0 0 80 60" xmlns="http://www.w3.org/2000/svg"><rect width="80" height="60" fill="${F}"/><rect x="16" y="20" width="48" height="20" rx="4" fill="none" stroke="${S}" stroke-width="1.5"/><rect x="24" y="27" width="32" height="6" rx="1" fill="${S}"/></svg>`,
    content: `<button class="px-6 py-3 rounded-lg border border-gray-300 text-gray-700 font-semibold text-sm hover:border-gray-500 transition-colors">Learn more</button>`,
  },
  {
    id: 'app-accordion',
    label: 'Accordion',
    category: 'Interactive',
    media: `<svg viewBox="0 0 80 60" xmlns="http://www.w3.org/2000/svg"><rect width="80" height="60" fill="${F}"/><rect x="6" y="8" width="68" height="12" rx="2" fill="${S}" opacity="0.5"/><rect x="10" y="13" width="40" height="3" rx="0.5" fill="${S}"/><rect x="6" y="23" width="68" height="12" rx="2" fill="rgba(255,255,255,0.04)" stroke="${S}" stroke-width="0.5"/><rect x="6" y="38" width="68" height="12" rx="2" fill="rgba(255,255,255,0.04)" stroke="${S}" stroke-width="0.5"/></svg>`,
    content: `<div class="divide-y divide-gray-200 border border-gray-200 rounded-xl overflow-hidden"><details class="group"><summary class="flex items-center justify-between px-5 py-4 cursor-pointer bg-white hover:bg-gray-50 font-medium text-gray-900 select-none">Question one<span class="text-gray-400 group-open:rotate-180 transition-transform">↓</span></summary><div class="px-5 py-4 bg-gray-50 text-gray-600 text-sm leading-relaxed">Answer content goes here. Replace this with your actual answer text.</div></details><details class="group"><summary class="flex items-center justify-between px-5 py-4 cursor-pointer bg-white hover:bg-gray-50 font-medium text-gray-900 select-none">Question two<span class="text-gray-400 group-open:rotate-180 transition-transform">↓</span></summary><div class="px-5 py-4 bg-gray-50 text-gray-600 text-sm leading-relaxed">Answer content goes here.</div></details></div>`,
  },
  {
    id: 'app-progress-bar',
    label: 'Progress Bar',
    category: 'Interactive',
    media: `<svg viewBox="0 0 80 60" xmlns="http://www.w3.org/2000/svg"><rect width="80" height="60" fill="${F}"/><rect x="6" y="26" width="68" height="8" rx="4" fill="rgba(255,255,255,0.06)"/><rect x="6" y="26" width="44" height="8" rx="4" fill="${G}" opacity="0.7"/></svg>`,
    content: `<div class="space-y-2"><div class="flex items-center justify-between text-sm text-gray-600 mb-1"><span>Progress</span><span>65%</span></div><div class="w-full bg-gray-200 rounded-full h-2.5"><div class="bg-green-600 h-2.5 rounded-full" style="width: 65%"></div></div></div>`,
  },
  {
    id: 'app-slider',
    label: 'Slider',
    category: 'Interactive',
    media: `<svg viewBox="0 0 80 60" xmlns="http://www.w3.org/2000/svg"><rect width="80" height="60" fill="${F}"/><rect x="6" y="28" width="68" height="4" rx="2" fill="rgba(255,255,255,0.1)"/><rect x="6" y="28" width="38" height="4" rx="2" fill="${G}" opacity="0.7"/><circle cx="44" cy="30" r="6" fill="${G}"/></svg>`,
    content: `<div class="space-y-3"><label class="block text-sm font-medium text-gray-700">Slider value: <span>50</span></label><input type="range" min="0" max="100" value="50" class="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-green-600"/></div>`,
  },

  // ── Media ─────────────────────────────────────────────────────────────────
  {
    id: 'app-divider',
    label: 'Divider',
    category: 'Media',
    media: `<svg viewBox="0 0 80 60" xmlns="http://www.w3.org/2000/svg"><rect width="80" height="60" fill="${F}"/><line x1="6" y1="30" x2="74" y2="30" stroke="${S}" stroke-width="1"/></svg>`,
    content: `<hr class="my-8 border-t border-gray-200"/>`,
  },
  {
    id: 'app-spacer',
    label: 'Spacer',
    category: 'Media',
    media: `<svg viewBox="0 0 80 60" xmlns="http://www.w3.org/2000/svg"><rect width="80" height="60" fill="${F}"/><line x1="6" y1="18" x2="74" y2="18" stroke="${S}" stroke-width="0.5" stroke-dasharray="3 3"/><line x1="6" y1="42" x2="74" y2="42" stroke="${S}" stroke-width="0.5" stroke-dasharray="3 3"/><line x1="40" y1="22" x2="40" y2="38" stroke="${S}" stroke-width="1"/></svg>`,
    content: `<div class="w-full" style="height: 64px"></div>`,
  },
  {
    id: 'app-video-embed',
    label: 'Video',
    category: 'Media',
    media: `<svg viewBox="0 0 80 60" xmlns="http://www.w3.org/2000/svg"><rect width="80" height="60" fill="${F}"/><rect x="6" y="10" width="68" height="40" rx="3" fill="rgba(255,255,255,0.04)" stroke="${S}" stroke-width="0.8"/><circle cx="40" cy="30" r="10" fill="rgba(255,255,255,0.08)"/><polygon points="37,25 37,35 47,30" fill="${G}" opacity="0.8"/></svg>`,
    content: `<div class="relative w-full aspect-video rounded-xl overflow-hidden bg-gray-900"><iframe src="https://www.youtube.com/embed/dQw4w9WgXcQ" title="Video" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen class="absolute inset-0 w-full h-full border-0"></iframe></div>`,
  },

  // ── Additional Layout ─────────────────────────────────────────────────────
  {
    id: 'app-stats-row',
    label: 'Stats Row',
    category: 'Layout',
    media: `<svg viewBox="0 0 80 60" xmlns="http://www.w3.org/2000/svg"><rect width="80" height="60" fill="${F}"/><rect x="4" y="14" width="22" height="32" rx="2" fill="rgba(255,255,255,0.04)" stroke="${S}" stroke-width="0.8"/><rect x="8" y="22" width="14" height="7" rx="1" fill="${S}"/><rect x="8" y="33" width="10" height="3" rx="0.5" fill="rgba(255,255,255,0.07)"/><rect x="29" y="14" width="22" height="32" rx="2" fill="rgba(255,255,255,0.04)" stroke="${S}" stroke-width="0.8"/><rect x="33" y="22" width="14" height="7" rx="1" fill="${S}"/><rect x="33" y="33" width="10" height="3" rx="0.5" fill="rgba(255,255,255,0.07)"/><rect x="54" y="14" width="22" height="32" rx="2" fill="rgba(255,255,255,0.04)" stroke="${S}" stroke-width="0.8"/><rect x="58" y="22" width="14" height="7" rx="1" fill="${S}"/><rect x="58" y="33" width="10" height="3" rx="0.5" fill="rgba(255,255,255,0.07)"/></svg>`,
    content: `<section class="py-16 px-8 bg-white"><div class="max-w-4xl mx-auto grid grid-cols-3 gap-8 text-center">${['10k+|Projects', '99.9%|Uptime', '<200ms|Response'].map(s => { const [n, l] = s.split('|'); return `<div><div class="text-4xl font-extrabold text-gray-900 mb-2">${n}</div><div class="text-gray-500 text-sm font-medium">${l}</div></div>`; }).join('')}</div></section>`,
  },
  {
    id: 'app-cta-banner',
    label: 'CTA Banner',
    category: 'Layout',
    media: `<svg viewBox="0 0 80 60" xmlns="http://www.w3.org/2000/svg"><rect width="80" height="60" fill="rgba(255,255,255,0.06)"/><rect x="8" y="14" width="48" height="6" rx="1" fill="${S}"/><rect x="14" y="24" width="36" height="3" rx="0.5" fill="rgba(255,255,255,0.07)"/><rect x="18" y="36" width="20" height="8" rx="2" fill="${G}" opacity="0.7"/></svg>`,
    content: `<section class="py-20 px-8 bg-gray-900 text-center"><div class="max-w-2xl mx-auto"><h2 class="text-3xl font-bold text-white mb-4">Ready to get started?</h2><p class="text-gray-400 mb-8">Join thousands of teams shipping faster with our platform.</p><a href="#" class="inline-block px-8 py-3 rounded-xl bg-green-600 text-white font-semibold hover:bg-green-500 transition-colors">Get started free</a></div></section>`,
  },

  // ── Additional Forms ──────────────────────────────────────────────────────
  {
    id: 'app-search-bar',
    label: 'Search Bar',
    category: 'Forms',
    media: `<svg viewBox="0 0 80 60" xmlns="http://www.w3.org/2000/svg"><rect width="80" height="60" fill="${F}"/><rect x="6" y="22" width="52" height="16" rx="3" fill="rgba(255,255,255,0.04)" stroke="${S}" stroke-width="0.8"/><circle cx="18" cy="30" r="4" fill="none" stroke="${S}" stroke-width="1"/><line x1="21" y1="33" x2="24" y2="36" stroke="${S}" stroke-width="1"/><rect x="62" y="22" width="12" height="16" rx="2" fill="${G}" opacity="0.7"/></svg>`,
    content: `<div class="flex items-center gap-2 max-w-xl mx-auto"><div class="relative flex-1"><svg class="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><circle cx="11" cy="11" r="7"/><path d="m21 21-4.35-4.35"/></svg><input type="search" placeholder="Search..." class="w-full pl-10 pr-4 py-3 rounded-lg border border-gray-300 focus:outline-none focus:border-green-500 text-sm"/></div><button class="px-5 py-3 rounded-lg bg-green-600 text-white font-semibold text-sm hover:bg-green-500 transition-colors">Search</button></div>`,
  },
];

export const CATEGORIES = ['Layout', 'Nav', 'Hero', 'Cards', 'Forms', 'Footer', 'Typography', 'Interactive', 'Media'] as const;
