// FlezPay Enterprise — Landing Page Scripts
// Theme Toggle, Flip Stack, Carousel, Reveal Animations, FAQ, Mobile Menu

document.addEventListener('DOMContentLoaded', () => {
    // ──────────────────────────────────────────────
    // Initialize Lucide Icons
    // ──────────────────────────────────────────────
    if (window.lucide) {
        window.lucide.createIcons();
    }

    // ──────────────────────────────────────────────
    // Theme Toggle (Dark / Light)
    // ──────────────────────────────────────────────
    const themeToggle = document.getElementById('themeToggle');
    const html = document.documentElement;

    // Load saved preference
    const savedTheme = localStorage.getItem('theme') || 'dark';
    html.setAttribute('data-theme', savedTheme);
    html.classList.remove('light', 'dark');
    html.classList.add(savedTheme);

    if (themeToggle) {
        themeToggle.addEventListener('click', () => {
            const current = html.getAttribute('data-theme');
            const next = current === 'dark' ? 'light' : 'dark';
            html.setAttribute('data-theme', next);
            html.classList.remove('light', 'dark');
            html.classList.add(next);
            localStorage.setItem('theme', next);
            // Re-initialize lucide icons so theme toggle icons update
            if (window.lucide) lucide.createIcons();
        });
    }

    // ──────────────────────────────────────────────
    // Scroll Reveal Animations
    // ──────────────────────────────────────────────
    const revealObserver = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('reveal');
            }
        });
    }, { threshold: 0.1 });

    document.querySelectorAll('.reveal-hidden').forEach(el => revealObserver.observe(el));

    // ──────────────────────────────────────────────
    // Navbar Scroll Effect
    // ──────────────────────────────────────────────
    const navbar = document.querySelector('.navbar');
    if (navbar) {
        const onScroll = () => {
            navbar.classList.toggle('scrolled', window.scrollY > 50);
        };
        window.addEventListener('scroll', onScroll, { passive: true });
        onScroll();
    }

    // ──────────────────────────────────────────────
    // Flip Stack — Scroll-Driven Card Flip Animation
    // ──────────────────────────────────────────────
    const flipStack = document.getElementById('flipStack');
    const flipCards = document.querySelectorAll('.flip-card');
    const flipNav = document.getElementById('flipNav');
    const flipNavItems = document.querySelectorAll('.flip-nav-item');

    if (flipStack && flipCards.length > 1) {
        let currentFlipIndex = 0;

        const updateFlipCards = () => {
            const rect = flipStack.getBoundingClientRect();
            const containerTop = -rect.top;
            const containerHeight = flipStack.offsetHeight - window.innerHeight;

            if (containerHeight <= 0) return;

            const scrollProgress = Math.max(0, Math.min(1, containerTop / containerHeight));

            const numCards = flipCards.length;
            const numTransitions = numCards - 1;

            // Show/hide flip nav indicator
            if (flipNav) {
                const inView = containerTop >= -100 && containerTop <= containerHeight + 100;
                flipNav.classList.toggle('visible', inView);
            }

            flipCards.forEach((card, i) => {
                const startSlide = Math.max(0, (i - 1) / numTransitions);
                const completeSlide = i / numTransitions;
                const completeCover = (i + 1) / numTransitions;
                
                let slideProgress = 0;
                let coverProgress = 0;
                
                if (i === 0) {
                    slideProgress = 1;
                    if (scrollProgress <= completeCover) coverProgress = scrollProgress / completeCover;
                    else coverProgress = 1;
                } else {
                    if (scrollProgress < startSlide) slideProgress = 0;
                    else if (scrollProgress >= startSlide && scrollProgress <= completeSlide) {
                        slideProgress = (scrollProgress - startSlide) / (completeSlide - startSlide);
                    } else if (scrollProgress > completeSlide) {
                        slideProgress = 1;
                        if (i < numCards - 1) {
                            if (scrollProgress <= completeCover) {
                                coverProgress = (scrollProgress - completeSlide) / (completeCover - completeSlide);
                            } else {
                                coverProgress = 1;
                            }
                        }
                    }
                }

                // Add a small delay/deadzone so the card stays un-scaled briefly while reading
                const adjustedCover = Math.max(0, (coverProgress - 0.2) / 0.8);
                
                const translateY = (1 - slideProgress) * 100;
                const scale = 1 - (adjustedCover * 0.05);
                const opacity = 1 - (adjustedCover * 0.6);

                card.style.transform = `translateY(${translateY}vh) scale(${scale})`;
                card.style.opacity = String(opacity);
                card.style.pointerEvents = (slideProgress < 0.9 || coverProgress > 0.5) ? 'none' : 'auto';
            });

            // Determine which card is currently active (frontmost visible)
            let activeIndex = 0;
            for (let i = 0; i < numCards; i++) {
                const start = i === 0 ? 0 : i / numTransitions;
                if (scrollProgress >= start + 0.15 / numTransitions) {
                    activeIndex = i;
                }
            }
            // Clamp
            activeIndex = Math.min(activeIndex, numCards - 1);

            if (activeIndex !== currentFlipIndex) {
                currentFlipIndex = activeIndex;
                flipNavItems.forEach((item, i) => {
                    item.classList.toggle('active', i === activeIndex);
                });
            }
        };

        window.addEventListener('scroll', updateFlipCards, { passive: true });
        window.addEventListener('resize', updateFlipCards, { passive: true });
        updateFlipCards(); // Initial call

        // Click on flip nav to scroll to card
        flipNavItems.forEach((item, i) => {
            item.addEventListener('click', () => {
                const containerRect = flipStack.getBoundingClientRect();
                const containerHeight = flipStack.offsetHeight - window.innerHeight;
                const numTransitions = flipCards.length - 1;
                const targetProgress = i / numTransitions;
                const targetScroll = flipStack.offsetTop + (targetProgress * containerHeight);

                window.scrollTo({
                    top: targetScroll,
                    behavior: 'smooth'
                });
            });
        });
    }

    // ──────────────────────────────────────────────
    // Coverflow Carousel (Testimonials)
    // ──────────────────────────────────────────────
    class CoverflowCarousel {
        constructor() {
            this.wrapper = document.getElementById('carouselWrapper');
            this.cards = Array.from(document.querySelectorAll('.coverflow-card'));
            this.prevBtn = document.getElementById('prevBtn');
            this.nextBtn = document.getElementById('nextBtn');
            this.dotsContainer = document.getElementById('carouselDots');

            if (!this.wrapper || this.cards.length === 0) return;

            this.currentIndex = 1;
            this.isDragging = false;
            this.startX = 0;

            this.init();
        }

        init() {
            // Create dots
            this.cards.forEach((_, i) => {
                const dot = document.createElement('div');
                dot.classList.add('carousel-dot');
                if (i === this.currentIndex) dot.classList.add('active');
                dot.addEventListener('click', () => this.goTo(i));
                this.dotsContainer.appendChild(dot);
            });

            this.update();

            // Button events
            this.prevBtn.addEventListener('click', () => this.prev());
            this.nextBtn.addEventListener('click', () => this.next());

            // Touch & mouse drag
            const container = document.querySelector('.coverflow-container');
            if (container) {
                container.addEventListener('mousedown', (e) => this.dragStart(e));
                container.addEventListener('touchstart', (e) => this.dragStart(e), { passive: true });
                window.addEventListener('mousemove', (e) => this.dragMove(e));
                window.addEventListener('touchmove', (e) => this.dragMove(e), { passive: false });
                window.addEventListener('mouseup', () => this.dragEnd());
                window.addEventListener('touchend', () => this.dragEnd());
            }

            window.addEventListener('resize', () => this.update());

            // Auto-play
            this.autoPlayInterval = setInterval(() => this.next(), 5000);
            if (container) {
                container.addEventListener('mouseenter', () => clearInterval(this.autoPlayInterval));
                container.addEventListener('mouseleave', () => {
                    this.autoPlayInterval = setInterval(() => this.next(), 5000);
                });
            }
        }

        update() {
            const isMobile = window.innerWidth < 768;
            const cardWidth = this.cards[0].offsetWidth;

            this.cards.forEach((card, i) => {
                const diff = i - this.currentIndex;
                const spacing = isMobile ? cardWidth * 0.15 : cardWidth * 0.45;
                const xTranslate = diff * spacing;
                const zTranslate = Math.abs(diff) * (isMobile ? -150 : -250);
                const rotateY = diff * (isMobile ? -25 : -40);
                let scale = 1 - Math.abs(diff) * (isMobile ? 0.1 : 0.15);
                let opacity = 1 - Math.abs(diff) * (isMobile ? 0.7 : 0.6);

                if (diff === 0) {
                    scale = isMobile ? 1.05 : 1.1;
                    opacity = 1;
                }

                card.style.transform = `translateX(${xTranslate}px) translateZ(${zTranslate}px) rotateY(${rotateY}deg) scale(${scale})`;
                card.style.opacity = Math.max(opacity, 0);
                card.style.zIndex = 100 - Math.abs(diff);
            });

            // Update dots
            const dots = this.dotsContainer.querySelectorAll('.carousel-dot');
            dots.forEach((dot, i) => {
                dot.classList.toggle('active', i === this.currentIndex);
            });
        }

        next() {
            this.currentIndex = (this.currentIndex + 1) % this.cards.length;
            this.update();
        }

        prev() {
            this.currentIndex = (this.currentIndex - 1 + this.cards.length) % this.cards.length;
            this.update();
        }

        goTo(index) {
            this.currentIndex = index;
            this.update();
        }

        dragStart(e) {
            this.isDragging = true;
            this.startX = e.type.includes('touch') ? e.touches[0].clientX : e.clientX;
        }

        dragMove(e) {
            if (!this.isDragging) return;
            const currentX = e.type.includes('touch') ? e.touches[0].clientX : e.clientX;
            const diff = currentX - this.startX;

            if (Math.abs(diff) > 50) {
                if (diff > 0) this.prev();
                else this.next();
                this.dragEnd();
            }
        }

        dragEnd() {
            this.isDragging = false;
        }
    }

    new CoverflowCarousel();

    // ──────────────────────────────────────────────
    // FAQ Accordion
    // ──────────────────────────────────────────────
    document.querySelectorAll('.faq-question').forEach(btn => {
        btn.addEventListener('click', () => {
            const item = btn.closest('.faq-item');
            const isOpen = item.classList.contains('open');

            // Close all items
            document.querySelectorAll('.faq-item').forEach(i => i.classList.remove('open'));

            // Open clicked item (if it wasn't already open)
            if (!isOpen) {
                item.classList.add('open');
            }
        });
    });

    // ──────────────────────────────────────────────
    // Mobile Menu
    // ──────────────────────────────────────────────
    const mobileMenuBtn = document.getElementById('mobileMenuBtn');
    const mobileMenuClose = document.getElementById('mobileMenuClose');
    const mobileMenu = document.getElementById('mobileMenu');

    if (mobileMenuBtn && mobileMenu) {
        mobileMenuBtn.addEventListener('click', () => {
            mobileMenu.classList.add('open');
        });

        if (mobileMenuClose) {
            mobileMenuClose.addEventListener('click', () => {
                mobileMenu.classList.remove('open');
            });
        }

        // Close menu when a link is clicked
        mobileMenu.querySelectorAll('a').forEach(link => {
            link.addEventListener('click', () => {
                mobileMenu.classList.remove('open');
            });
        });
    }

    // ──────────────────────────────────────────────
    // Smooth scroll for anchor links
    // ──────────────────────────────────────────────
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            const href = this.getAttribute('href');
            if (href === '#') return;

            e.preventDefault();
            const target = document.querySelector(href);
            if (target) {
                const offset = 100; // Account for fixed navbar
                const top = target.getBoundingClientRect().top + window.pageYOffset - offset;
                window.scrollTo({ top, behavior: 'smooth' });
            }
        });
    });
});
