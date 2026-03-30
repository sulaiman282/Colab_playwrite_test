#!/usr/bin/env python3
"""
Browser Flow Service for Colab
Handles post-registration browser flow: homepage → login → view-profile → MFA
Optimized for headless operation in Google Colab
"""

import asyncio
import logging
import time
import os
from typing import Optional, Tuple

from playwright.async_api import async_playwright, Browser, Page, BrowserContext

from config import config
from models import AccountData, AccountStatus

logger = logging.getLogger(__name__)


class BrowserFlowService:
    def __init__(self, worker_id: str = "default", headless: bool = True):
        self.worker_id = worker_id
        self.headless = headless
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None

        timestamp = int(time.time())
        self.profile_name = f"{worker_id}_api_{timestamp}"
        self.profile_path = os.path.join(config.storage.profiles_dir, self.profile_name)
        os.makedirs(self.profile_path, exist_ok=True)

    async def start_browser(self, headless: bool = None) -> bool:
        if headless is None:
            headless = self.headless
        try:
            self.playwright = await async_playwright().start()

            # AGGRESSIVE COLAB OPTIMIZATIONS
            optimized_args = [
                # Core sandboxing
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-accelerated-2d-canvas',
                '--no-first-run',
                '--no-zygote',
                
                # GPU/Memory optimization
                '--disable-gpu',
                '--disable-gpu-compositing',
                '--disable-gpu-rasterization',
                '--disable-software-rasterizer',
                '--disable-gpu-sandbox',
                
                # Disable features we don't need
                '--disable-extensions',
                '--disable-plugins',
                '--disable-images',
                '--disable-web-security',
                '--disable-webgl',
                '--disable-webgl2',
                '--disable-webaudio',
                '--disable-background-networking',
                '--disable-background-timer-throttling',
                '--disable-backgrounding-occluded-windows',
                '--disable-renderer-backgrounding',
                '--disable-hang-monitor',
                '--disable-ipc-flooding-protection',
                '--disable-popup-blocking',
                '--disable-prompt-on-repost',
                '--disable-sync',
                '--disable-translate',
                '--metrics-recording-only',
                '--mute-audio',
                '--no-default-browser-check',
                '--no-experiments',
                '--no-pingsend',
                '--no-zygote',
                
                # Automation detection prevention (minimal)
                '--disable-blink-features=AutomationControlled',
                
                # Window and rendering
                '--window-size=1280,720',
                '--force-color-profile=srgb',
                
                # Resource blocking at browser level
                '--blink-settings=imagesEnabled=false',
                '--disable-image-loading',
                '--disable-image-resize',
                
                # Connection optimizations
                '--disable-default-apps',
                '--disable-breakpad',
                '--disable-logging',
                '--log-level=3',
                '--ignore-certificate-errors',
                '--ignore-certificate-errors-spki-list',
                
                # Performance
                '--disable-features=TranslateUI,BlinkGenPropertyTrees',
                '--disable-ios-password-suggestions',
                '--disable-password-generation',
                '--enable-features=NetworkService,NetworkServiceInProcess',
                '--force-color-profile=srgb',
                '--max-space-for-cache=1024',
            ]

            self.browser = await self.playwright.chromium.launch(
                headless=headless,
                args=optimized_args,
                downloads_path=None,
            )

            # OPTIMIZED CONTEXT - Smaller viewport
            self.context = await self.browser.new_context(
                viewport={'width': 1280, 'height': 720},
                user_agent=config.browser.user_agent,
                java_script_enabled=True,
                ignore_https_errors=True,
                bypass_csp=True,
                locale='en-US',
                timezone_id='America/New_York',
                reduced_motion='reduce',
                color_scheme='light',
            )

            # AGGRESSIVE RESOURCE BLOCKING
            # Images - Block these aggressively
            for pattern in [
                "**/*.png", "**/*.jpg", "**/*.jpeg", "**/*.gif", "**/*.webp", 
                "**/*.ico", "**/*.bmp", "**/*.avif", "**/*.tiff",
                "**/images/*", "**/img/*", "**/media/*",
                "https://*.ctfassets.net/*",
                "https://*.dentalcare.com/*.png", "https://*.dentalcare.com/*.jpg",
                "https://*.dentalcare.com/*.jpeg", "https://*.dentalcare.com/*.gif",
                "https://*.dentalcare.com/*.webp",
                "https://*.google-analytics.com/**",
                "https://*.doubleclick.net/**",
            ]:
                await self.context.route(pattern, lambda route: route.abort())

            # Analytics and tracking
            await self.context.route("**/favicon*", lambda route: route.abort())
            await self.context.route("**/*analytics*", lambda route: route.abort())
            await self.context.route("**/*tracking*", lambda route: route.abort())
            await self.context.route("**/*pixel*", lambda route: route.abort())
            await self.context.route("**/*beacon*", lambda route: route.abort())
            await self.context.route("**/*hotjar*", lambda route: route.abort())
            await self.context.route("**/*segment*", lambda route: route.abort())
            await self.context.route("**/*mixpanel*", lambda route: route.abort())
            await self.context.route("**/*optimizely*", lambda route: route.abort())
            await self.context.route("**/*quantserve*", lambda route: route.abort())
            await self.context.route("**/*scorecardresearch*", lambda route: route.abort())

            # Videos and media
            await self.context.route("**/*.mp4", lambda route: route.abort())
            await self.context.route("**/*.webm", lambda route: route.abort())
            await self.context.route("**/*.mp3", lambda route: route.abort())
            await self.context.route("**/*.wav", lambda route: route.abort())

            # Fonts
            await self.context.route("**/*.woff", lambda route: route.abort())
            await self.context.route("**/*.woff2", lambda route: route.abort())
            await self.context.route("**/*.ttf", lambda route: route.abort())
            await self.context.route("**/*.otf", lambda route: route.abort())

            # SUPER AGGRESSIVE init script for blocking remaining resources
            await self.context.add_init_script("""
                // Block images at DOM level
                (function() {
                    // Block Image constructor
                    const OriginalImage = window.Image;
                    window.Image = function() {
                        const img = new OriginalImage();
                        Object.defineProperty(img, 'src', {
                            get: function() { return ''; },
                            set: function(v) { /* blocked */ }
                        });
                        return img;
                    };
                    window.Image.prototype = OriginalImage.prototype;

                    // Block HTMLImageElement
                    if (HTMLImageElement && HTMLImageElement.prototype) {
                        try {
                            Object.defineProperty(HTMLImageElement.prototype, 'src', {
                                get: function() { return ''; },
                                set: function(v) { /* blocked */ }
                            });
                        } catch(e) {}
                    }

                    // Block CSS background images
                    const style = document.createElement('style');
                    style.innerHTML = [
                        '*[style*="background-image"] { background-image: none !important; }',
                        '* { background-image: none !important; }',
                        'img { display: none !important; }',
                        'video { display: none !important; }',
                        'audio { display: none !important; }',
                    ].join('\\n');
                    (document.head || document.documentElement).appendChild(style);

                    // Block WebGL
                    try {
                        const getContext = HTMLCanvasElement.prototype.getContext;
                        HTMLCanvasElement.prototype.getContext = function(type) {
                            if (type === 'webgl' || type === 'webgl2' || type === 'experimental-webgl') {
                                return null;
                            }
                            return getContext.call(this, type);
                        };
                    } catch(e) {}

                    // Remove video/audio sources
                    document.querySelectorAll('video, audio').forEach(el => {
                        el.pause();
                        el.src = '';
                        el.load();
                    });

                    // Webdriver detection bypass
                    Object.defineProperty(navigator, 'webdriver', { get: () => false });
                    Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3] });
                    Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
                    window.chrome = { runtime: {} };
                })();
            """)

            logger.info(f"[BROWSER-FLOW] Browser started (headless={headless})")
            return True

        except Exception as e:
            logger.error(f"[BROWSER-FLOW] Failed to start browser: {e}")
            return False

    async def login_and_navigate(self, account: AccountData) -> Tuple[bool, Optional[str]]:
        try:
            logger.info(f"[BROWSER-FLOW] Starting flow for: {account.email}")

            if not self.browser:
                if not await self.start_browser():
                    return False, "Failed to start browser"

            self.page = await self.context.new_page()
            self.page.set_default_timeout(config.browser.timeout)

            await self._navigate_homepage()
            await self._click_login()
            await self._wait_login_page()
            await self._fill_credentials(account.email, account.password)
            await self._submit_login()
            await self._wait_redirect()
            mfa_reached = await self._navigate_view_profile()

            return True, None, mfa_reached

        except Exception as e:
            logger.error(f"[BROWSER-FLOW] Flow error: {e}")
            return False, str(e)

    async def _navigate_homepage(self) -> None:
        logger.info("[1/6] Navigating to homepage")
        await self.page.goto('https://www.dentalcare.com/en-us', wait_until='domcontentloaded', timeout=30000)
        await self.page.wait_for_timeout(1000)
        await self._handle_survey_popup()
        logger.info(f"[1/6] Homepage URL: {self.page.url}")

    async def _click_login(self) -> None:
        logger.info("[2/6] Clicking LOGIN button")
        login_selectors = [
            'button:has-text("LOGIN")', 'a:has-text("LOGIN")',
            'a:has-text("Log In")', 'a:has-text("Sign In")',
            'button:has-text("Sign In")', '[data-action-detail="LOGIN"]',
            'a[href*="login"]', '.login-btn', '#login-btn',
        ]
        for selector in login_selectors:
            try:
                btn = self.page.locator(selector).first
                if await btn.count() > 0 and await btn.is_visible():
                    await btn.click(force=True)
                    logger.info(f"[2/6] Clicked LOGIN via: {selector}")
                    await self.page.wait_for_timeout(3000)
                    return
            except:
                pass

        try:
            await self.page.evaluate("""
                () => {
                    const buttons = Array.from(document.querySelectorAll('button, a'));
                    const loginBtn = buttons.find(btn => {
                        const text = (btn.textContent || '').trim().toUpperCase();
                        return text === 'LOGIN' || text === 'SIGN IN' || text === 'LOG IN';
                    });
                    if (loginBtn) loginBtn.click();
                }
            """)
        except:
            pass

    async def _wait_login_page(self) -> None:
        logger.info("[3/6] Waiting for login page")
        await self.page.wait_for_timeout(2000)
        await self._handle_survey_popup()
        logger.info(f"[3/6] Login page URL: {self.page.url}")

    async def _fill_credentials(self, email: str, password: str) -> None:
        logger.info("[4/6] Filling credentials")
        try:
            result = await self.page.evaluate(f"""
                () => {{
                    const usernameInput = document.querySelector('#username, input[name="username"], input[type="email"], input[name="email"]');
                    const passwordInput = document.querySelector('#password, input[name="password"], input[type="password"]');

                    if (usernameInput && passwordInput) {{
                        usernameInput.value = '{email}';
                        usernameInput.dispatchEvent(new Event('input', {{ bubbles: true }}));
                        usernameInput.dispatchEvent(new Event('change', {{ bubbles: true }}));

                        passwordInput.value = '{password}';
                        passwordInput.dispatchEvent(new Event('input', {{ bubbles: true }}));
                        passwordInput.dispatchEvent(new Event('change', {{ bubbles: true }}));

                        return 'filled';
                    }}
                    return 'not-found';
                }}
            """)
            if result == 'filled':
                logger.info("[4/6] Credentials filled via JavaScript")
                return
        except:
            pass

        for email_sel, pass_sel in [
            ('#username', '#password'),
            ('input[type="email"]', 'input[type="password"]'),
            ('input[name="username"]', 'input[name="password"]'),
        ]:
            try:
                email_input = self.page.locator(email_sel).first
                pass_input = self.page.locator(pass_sel).first
                if await email_input.count() > 0 and await pass_input.count() > 0:
                    await email_input.fill(email)
                    await pass_input.fill(password)
                    logger.info(f"[4/6] Credentials filled via: {email_sel}")
                    return
            except:
                pass

    async def _submit_login(self) -> None:
        logger.info("[5/6] Clicking login submit")
        submit_selectors = [
            'button[name="action"]', 'button[type="submit"]',
            'button:has-text("Continue")', 'button:has-text("Login")',
            'button:has-text("Sign In")', 'input[type="submit"]',
        ]
        for selector in submit_selectors:
            try:
                btn = self.page.locator(selector).first
                if await btn.count() > 0:
                    await btn.click(force=True)
                    logger.info(f"[5/6] Clicked submit via: {selector}")
                    return
            except:
                pass
        try:
            await self.page.keyboard.press('Enter')
        except:
            pass

    async def _wait_redirect(self) -> None:
        logger.info("[6/6] Waiting for redirect")
        max_wait = 15
        start_time = time.time()
        while time.time() - start_time < max_wait:
            current_url = self.page.url
            if 'dentalcare.com/en-us' in current_url and '/auth' not in current_url:
                logger.info("[6/6] Reached homepage!")
                break
            await self.page.wait_for_timeout(500)

        await self.page.wait_for_timeout(1000)
        await self._handle_survey_popup()
        logger.info(f"[6/6] Final URL: {self.page.url}")

    async def _navigate_view_profile(self) -> bool:
        """Navigate to view-profile and click Edit to reach MFA"""
        logger.info("[7/9] Navigating to view-profile")
        await self.page.goto(
            'https://www.dentalcare.com/en-us/user-account/view-profile',
            wait_until='domcontentloaded',
            timeout=30000
        )
        await self.page.wait_for_timeout(2000)
        await self._handle_survey_popup()
        logger.info(f"[7/9] View profile URL: {self.page.url}")
        
        # Click Edit to reach MFA
        mfa_reached = await self._click_edit()
        return mfa_reached

    async def _click_edit(self) -> bool:
        """Click Edit button and wait for MFA page navigation"""
        logger.info("[8/9] Clicking Edit to reach MFA")
        
        # First, scroll to top to ensure Edit button is visible
        await self.page.evaluate("window.scrollTo(0, 0);")
        await self.page.wait_for_timeout(300)
        
        # First try direct MFA link (most reliable)
        try:
            mfa_link = self.page.locator('a[href*="mfa-sms-enrollment"]').first
            if await mfa_link.count() > 0:
                await mfa_link.click(force=True)
                await self.page.wait_for_timeout(2000)
                if 'mfa' in self.page.url:
                    logger.info("[8/9] Successfully reached MFA page via direct link")
                    return True
        except:
            pass
        
        # Try Edit button
        edit_selectors = [
            'a[href*="mfa-sms-enrollment"]',
            'a:has-text("Edit Profile")', 'button:has-text("Edit Profile")',
            'a[aria-label*="Edit Profile"]', 'a:has-text("Edit")',
            'button:has-text("Edit")', 'a[aria-label*="Edit"]',
            'button[aria-label*="Edit"]', '[role="button"]:has-text("Edit")',
        ]
        
        for selector in edit_selectors:
            try:
                el = self.page.locator(selector).first
                if await el.count() > 0:
                    await el.scroll_into_view_if_needed()
                    await el.click(force=True)
                    logger.info(f"[8/9] Clicked Edit via: {selector}")
                    # Wait for MFA page to load
                    await self.page.wait_for_timeout(2000)
                    
                    # Check if we're on MFA page
                    if 'mfa' in self.page.url:
                        logger.info(f"[8/9] Successfully reached MFA page: {self.page.url}")
                        return True
                    continue
            except:
                pass

        # Try JavaScript click with MFA href detection
        try:
            result = await self.page.evaluate("""
                () => {
                    // Try direct MFA link first
                    const mfaLink = document.querySelector('a[href*="mfa"]');
                    if (mfaLink) {
                        mfaLink.click();
                        return 'mfa-href';
                    }
                    // Try to find Edit button by text
                    const allElements = document.querySelectorAll('a, button, [role="button"]');
                    for (const el of allElements) {
                        const text = (el.textContent || '').trim().toLowerCase();
                        if (text === 'edit profile' || text === 'edit') {
                            el.scrollIntoView();
                            el.click();
                            return 'clicked:' + text;
                        }
                    }
                    return 'not-found';
                }
            """)
            if result != 'not-found':
                logger.info(f"[8/9] Edit clicked via JS: {result}")
                await self.page.wait_for_timeout(2000)
                if 'mfa' in self.page.url:
                    logger.info(f"[8/9] Successfully reached MFA page: {self.page.url}")
                    return True
        except:
            pass

        logger.info(f"[8/9] Current URL: {self.page.url}")
        return 'mfa' in self.page.url

    async def _handle_survey_popup(self) -> None:
        try:
            await self.page.wait_for_timeout(500)
            await self.page.evaluate("""
                const selectors = ['.QSIWebResponsive', '[class*="survey"]', '[id*="survey"]',
                    'iframe[title*="Survey"]', '[class*="qualtrics"]', '[class*="feedback"]'];
                selectors.forEach(sel => {
                    document.querySelectorAll(sel).forEach(el => {
                        try { el.remove(); } catch(e) { el.style.display = 'none'; }
                    });
                });
            """)
        except:
            pass

    def get_page(self) -> Optional[Page]:
        return self.page

    async def stop_browser(self) -> None:
        try:
            if self.context:
                await self.context.close()
                self.context = None
            if self.browser:
                await self.browser.close()
                self.browser = None
            if self.playwright:
                await self.playwright.stop()
                self.playwright = None
            logger.info(f"[BROWSER-FLOW] Browser stopped")
        except Exception as e:
            logger.error(f"[BROWSER-FLOW] Error stopping browser: {e}")
