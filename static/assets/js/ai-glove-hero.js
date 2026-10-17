/**
 * FlezPay Hero - Futuristic AI Intelligence Glove Visualizer
 * High-Tech Cybernetic Holographic Glove & Neural Network Constellation
 */

(function () {
    'use strict';

    const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const container = document.getElementById('hero-ai-canvas-container');
    if (!container) return;

    if (typeof THREE === 'undefined') {
        console.warn('Three.js not loaded. Hero AI glove visual fallback active.');
        return;
    }

    let scene, camera, renderer;
    let gloveMesh, neuralCloud, connectionLines;
    let particlePositions, particleVelocities, particleCount;
    let animationFrameId;
    let mouse = { x: 0, y: 0, targetX: 0, targetY: 0 };
    let isDarkMode = document.documentElement.classList.contains('dark');
    let isMobile = window.innerWidth < 768;

    const CONFIG = {
        primaryColorDark: 0x10b981,   // FlezPay Emerald
        secondaryColorDark: 0x06b6d4, // Subtle Cyan
        wireColorDark: 0x34d399,

        primaryColorLight: 0x059669,
        secondaryColorLight: 0x0284c7,
        wireColorLight: 0x10b981,

        maxParticlesDesktop: 350,
        maxParticlesMobile: 120,
        connectionDistance: 3.2
    };

    function init() {
        scene = new THREE.Scene();

        const aspect = container.clientWidth / container.clientHeight;
        camera = new THREE.PerspectiveCamera(45, aspect, 0.1, 100);
        camera.position.set(0, 0, 12);

        renderer = new THREE.WebGLRenderer({
            alpha: true,
            antialias: true,
            powerPreference: 'high-performance'
        });
        renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.5));
        renderer.setSize(container.clientWidth, container.clientHeight);
        renderer.outputEncoding = THREE.sRGBEncoding;
        container.appendChild(renderer.domElement);

        // Lights
        setupLights();

        // 1. Load High-Tech AI Glove Texture
        const textureLoader = new THREE.TextureLoader();
        const gloveTextureUrl = '/static/assets/image/ai-glove-hero.webp';

        textureLoader.load(
            gloveTextureUrl,
            function (texture) {
                texture.generateMipmaps = true;
                texture.minFilter = THREE.LinearMipmapLinearFilter;

                const gloveGeo = new THREE.PlaneGeometry(isMobile ? 8.5 : 12.0, isMobile ? 4.8 : 6.75);
                const gloveMat = new THREE.MeshBasicMaterial({
                    map: texture,
                    transparent: true,
                    opacity: isDarkMode ? 0.35 : 0.18,
                    depthWrite: false,
                    blending: THREE.AdditiveBlending
                });

                gloveMesh = new THREE.Mesh(gloveGeo, gloveMat);
                // Positioned on the right side on desktop for perfect balance behind hero copy
                gloveMesh.position.set(isMobile ? 0 : 2.5, isMobile ? 0.2 : 0.4, 0);
                scene.add(gloveMesh);
            },
            undefined,
            function () {
                console.warn('AI glove texture load fallback.');
            }
        );

        // 2. Build 3D Neural Constellation Network
        buildNeuralParticleField();

        // Events
        if (!isMobile && !prefersReducedMotion) {
            window.addEventListener('mousemove', onMouseMove, { passive: true });
        }
        window.addEventListener('resize', onWindowResize, { passive: true });

        // Dark mode observer
        const observer = new MutationObserver(() => {
            const currentDark = document.documentElement.classList.contains('dark');
            if (currentDark !== isDarkMode) {
                isDarkMode = currentDark;
                updateTheme();
            }
        });
        observer.observe(document.documentElement, { attributes: true, attributeFilter: ['class'] });

        animate(0);
    }

    let ambientLight, pointLight;

    function setupLights() {
        ambientLight = new THREE.AmbientLight(isDarkMode ? 0x064e3b : 0xe0f2fe, isDarkMode ? 1.5 : 0.8);
        scene.add(ambientLight);

        pointLight = new THREE.PointLight(isDarkMode ? 0x10b981 : 0x059669, isDarkMode ? 2.0 : 1.2, 30);
        pointLight.position.set(3, 4, 5);
        scene.add(pointLight);
    }

    function buildNeuralParticleField() {
        particleCount = isMobile ? CONFIG.maxParticlesMobile : CONFIG.maxParticlesDesktop;

        const positions = new Float32Array(particleCount * 3);
        particleVelocities = [];

        const spreadX = isMobile ? 9 : 16;
        const spreadY = isMobile ? 7 : 10;
        const spreadZ = 8;

        for (let i = 0; i < particleCount; i++) {
            positions[i * 3]     = (Math.random() - 0.5) * spreadX;
            positions[i * 3 + 1] = (Math.random() - 0.5) * spreadY;
            positions[i * 3 + 2] = (Math.random() - 0.5) * spreadZ;

            particleVelocities.push({
                x: (Math.random() - 0.5) * 0.003,
                y: (Math.random() - 0.5) * 0.003,
                z: (Math.random() - 0.5) * 0.002
            });
        }

        particlePositions = positions;

        const particleGeo = new THREE.BufferGeometry();
        particleGeo.setAttribute('position', new THREE.BufferAttribute(positions, 3));

        // Particle texture sprite
        const canvas = document.createElement('canvas');
        canvas.width = 32;
        canvas.height = 32;
        const ctx = canvas.getContext('2d');
        const gradient = ctx.createRadialGradient(16, 16, 0, 16, 16, 16);
        gradient.addColorStop(0, 'rgba(52, 211, 153, 1)');
        gradient.addColorStop(0.35, 'rgba(16, 185, 129, 0.7)');
        gradient.addColorStop(1, 'rgba(6, 182, 212, 0)');
        ctx.fillStyle = gradient;
        ctx.fillRect(0, 0, 32, 32);

        const particleTexture = new THREE.CanvasTexture(canvas);

        const particleMat = new THREE.PointsMaterial({
            size: 0.24,
            map: particleTexture,
            transparent: true,
            opacity: isDarkMode ? 0.65 : 0.35,
            blending: THREE.AdditiveBlending,
            depthWrite: false
        });

        neuralCloud = new THREE.Points(particleGeo, particleMat);
        scene.add(neuralCloud);

        // Constellation Lines
        const maxLines = particleCount * 2;
        const linePositions = new Float32Array(maxLines * 6);
        const lineGeo = new THREE.BufferGeometry();
        lineGeo.setAttribute('position', new THREE.BufferAttribute(linePositions, 3));

        const lineMat = new THREE.LineBasicMaterial({
            color: isDarkMode ? CONFIG.wireColorDark : CONFIG.wireColorLight,
            transparent: true,
            opacity: isDarkMode ? 0.20 : 0.08,
            blending: THREE.AdditiveBlending,
            depthWrite: false
        });

        connectionLines = new THREE.LineSegments(lineGeo, lineMat);
        scene.add(connectionLines);
    }

    function updateNeuralConnections() {
        if (!connectionLines || !particlePositions) return;

        const positions = neuralCloud.geometry.attributes.position.array;
        const linePos = connectionLines.geometry.attributes.position.array;
        let lineIdx = 0;
        const maxLines = (particleCount * 2) * 6;
        const maxDistSq = CONFIG.connectionDistance * CONFIG.connectionDistance;

        const step = isMobile ? 3 : 2;
        for (let i = 0; i < particleCount; i += step) {
            const x1 = positions[i * 3];
            const y1 = positions[i * 3 + 1];
            const z1 = positions[i * 3 + 2];

            for (let j = i + 1; j < particleCount; j += step) {
                if (lineIdx >= maxLines - 6) break;

                const dx = x1 - positions[j * 3];
                const dy = y1 - positions[j * 3 + 1];
                const dz = z1 - positions[j * 3 + 2];
                const distSq = dx * dx + dy * dy + dz * dz;

                if (distSq < maxDistSq) {
                    linePos[lineIdx++] = x1;
                    linePos[lineIdx++] = y1;
                    linePos[lineIdx++] = z1;
                    linePos[lineIdx++] = positions[j * 3];
                    linePos[lineIdx++] = positions[j * 3 + 1];
                    linePos[lineIdx++] = positions[j * 3 + 2];
                }
            }
        }

        for (let k = lineIdx; k < maxLines; k++) {
            linePos[k] = 0;
        }

        connectionLines.geometry.attributes.position.needsUpdate = true;
    }

    function updateTheme() {
        if (gloveMesh && gloveMesh.material) {
            gloveMesh.material.opacity = isDarkMode ? 0.35 : 0.18;
        }
        if (neuralCloud && neuralCloud.material) {
            neuralCloud.material.opacity = isDarkMode ? 0.65 : 0.35;
        }
        if (connectionLines && connectionLines.material) {
            connectionLines.material.color.setHex(isDarkMode ? CONFIG.wireColorDark : CONFIG.wireColorLight);
            connectionLines.material.opacity = isDarkMode ? 0.20 : 0.08;
        }
    }

    function onMouseMove(e) {
        const rect = container.getBoundingClientRect();
        const clientX = e.clientX - rect.left;
        const clientY = e.clientY - rect.top;
        mouse.targetX = (clientX / rect.width - 0.5) * 2;
        mouse.targetY = (clientY / rect.height - 0.5) * 2;
    }

    function onWindowResize() {
        if (!container || !camera || !renderer) return;
        isMobile = window.innerWidth < 768;
        camera.aspect = container.clientWidth / container.clientHeight;
        camera.updateProjectionMatrix();
        renderer.setSize(container.clientWidth, container.clientHeight);

        if (gloveMesh) {
            gloveMesh.position.set(isMobile ? 0 : 2.5, isMobile ? 0.2 : 0.4, 0);
        }
    }

    let clock = new THREE.Clock();

    function animate(time) {
        animationFrameId = requestAnimationFrame(animate);
        const elapsedTime = clock.getElapsedTime();

        if (!prefersReducedMotion) {
            mouse.x += (mouse.targetX - mouse.x) * 0.04;
            mouse.y += (mouse.targetY - mouse.y) * 0.04;

            // Glove subtle floating oscillation and mouse tilt
            if (gloveMesh) {
                gloveMesh.position.y = (isMobile ? 0.2 : 0.4) + Math.sin(elapsedTime * 0.7) * 0.15;
                gloveMesh.rotation.z = Math.sin(elapsedTime * 0.4) * 0.02 + mouse.x * 0.03;
                gloveMesh.rotation.y = mouse.x * 0.06;
                gloveMesh.rotation.x = -mouse.y * 0.04;
            }

            // Move neural particles slowly
            if (neuralCloud && particlePositions) {
                const positions = neuralCloud.geometry.attributes.position.array;
                for (let i = 0; i < particleCount; i++) {
                    positions[i * 3]     += particleVelocities[i].x;
                    positions[i * 3 + 1] += particleVelocities[i].y;
                    positions[i * 3 + 2] += particleVelocities[i].z;

                    const boundX = isMobile ? 4.5 : 8;
                    const boundY = isMobile ? 3.5 : 5;
                    if (Math.abs(positions[i * 3]) > boundX) particleVelocities[i].x *= -1;
                    if (Math.abs(positions[i * 3 + 1]) > boundY) particleVelocities[i].y *= -1;
                }
                neuralCloud.geometry.attributes.position.needsUpdate = true;
            }

            if (Math.floor(time / 32) % 2 === 0) {
                updateNeuralConnections();
            }
        }

        renderer.render(scene, camera);
    }

    window.addEventListener('beforeunload', () => {
        if (animationFrameId) cancelAnimationFrame(animationFrameId);
        if (renderer) renderer.dispose();
    });

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
