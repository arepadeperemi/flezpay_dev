/**
 * FlezPay Hero - Futuristic AI Intelligence Globe Visualizer
 * Balanced & Elegant 3D Holographic AI Business Globe for Light & Dark Modes
 */

(function () {
    'use strict';

    const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const container = document.getElementById('hero-ai-canvas-container');
    if (!container) return;

    if (typeof THREE === 'undefined') {
        console.warn('Three.js not loaded. Hero AI globe visual skipped.');
        return;
    }

    let scene, camera, renderer;
    let globeGroup, earthSphere, wireSphere, orbitalRing1, orbitalRing2;
    let arcCurves = [], pulsePoints = [];
    let particleCloud;
    let animationFrameId;
    let mouse = { x: 0, y: 0, targetX: 0, targetY: 0 };
    let isDarkMode = document.documentElement.classList.contains('dark');
    let isMobile = window.innerWidth < 768;

    const CONFIG = {
        globeRadius: 3.5,
        primaryColorDark: 0x10b981,   // FlezPay Emerald
        secondaryColorDark: 0x06b6d4, // Cyan
        wireColorDark: 0x059669,
        coreColorDark: 0x022c22,

        primaryColorLight: 0x059669,   // Crisp Emerald
        secondaryColorLight: 0x0284c7, // Cyan
        wireColorLight: 0x10b981,
        coreColorLight: 0xa7f3d0
    };

    let materialsList = [];

    function init() {
        scene = new THREE.Scene();

        const aspect = container.clientWidth / container.clientHeight;
        camera = new THREE.PerspectiveCamera(45, aspect, 0.1, 100);
        camera.position.set(0, 0, 10.5);

        renderer = new THREE.WebGLRenderer({
            alpha: true,
            antialias: true,
            powerPreference: 'high-performance'
        });
        renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.5));
        renderer.setSize(container.clientWidth, container.clientHeight);
        renderer.outputEncoding = THREE.sRGBEncoding;
        container.appendChild(renderer.domElement);

        setupLights();

        globeGroup = new THREE.Group();
        globeGroup.position.set(0, 0, 0);
        scene.add(globeGroup);

        buildHolographicGlobe();
        buildGlobalHubsAndArcs();
        buildOrbitalRings();
        buildAtmosphericParticles();

        if (!isMobile && !prefersReducedMotion) {
            window.addEventListener('mousemove', onMouseMove, { passive: true });
        }
        window.addEventListener('resize', onWindowResize, { passive: true });

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

    let ambientLight, pointLight, cyanFillLight;

    function setupLights() {
        ambientLight = new THREE.AmbientLight(isDarkMode ? 0x022c22 : 0xd1fae5, isDarkMode ? 0.8 : 0.9);
        scene.add(ambientLight);

        pointLight = new THREE.PointLight(isDarkMode ? CONFIG.primaryColorDark : CONFIG.primaryColorLight, isDarkMode ? 1.4 : 1.8, 25);
        pointLight.position.set(4, 5, 7);
        scene.add(pointLight);

        cyanFillLight = new THREE.PointLight(isDarkMode ? CONFIG.secondaryColorDark : CONFIG.secondaryColorLight, isDarkMode ? 1.0 : 1.3, 20);
        cyanFillLight.position.set(-5, -3, 5);
        scene.add(cyanFillLight);
    }

    function latLongToVector3(lat, lon, radius) {
        const phi = (90 - lat) * (Math.PI / 180);
        const theta = (lon + 180) * (Math.PI / 180);
        return new THREE.Vector3(
            -radius * Math.sin(phi) * Math.cos(theta),
            radius * Math.cos(phi),
            radius * Math.sin(phi) * Math.sin(theta)
        );
    }

    function buildHolographicGlobe() {
        const r = CONFIG.globeRadius;

        // 1. Inner Core
        const coreGeo = new THREE.SphereGeometry(r * 0.96, 32, 32);
        const coreMat = new THREE.MeshStandardMaterial({
            color: isDarkMode ? CONFIG.coreColorDark : CONFIG.coreColorLight,
            emissive: isDarkMode ? CONFIG.primaryColorDark : CONFIG.primaryColorLight,
            emissiveIntensity: isDarkMode ? 0.10 : 0.10,
            roughness: 0.35,
            metalness: 0.75,
            transparent: true,
            opacity: isDarkMode ? 0.18 : 0.20,
            depthWrite: false
        });
        materialsList.push(coreMat);
        earthSphere = new THREE.Mesh(coreGeo, coreMat);
        globeGroup.add(earthSphere);

        // 2. Wireframe Matrix
        const wireGeo = new THREE.SphereGeometry(r, 24, 24);
        const wireMat = new THREE.MeshBasicMaterial({
            color: isDarkMode ? CONFIG.wireColorDark : CONFIG.wireColorLight,
            wireframe: true,
            transparent: true,
            opacity: isDarkMode ? 0.15 : 0.22,
            depthWrite: false
        });
        materialsList.push(wireMat);
        wireSphere = new THREE.Mesh(wireGeo, wireMat);
        globeGroup.add(wireSphere);

        // 3. Dot Matrix Nodes
        const dotCount = isMobile ? 350 : 650;
        const dotPositions = new Float32Array(dotCount * 3);
        for (let i = 0; i < dotCount; i++) {
            const u = Math.random();
            const v = Math.random();
            const theta = u * 2.0 * Math.PI;
            const phi = Math.acos(2.0 * v - 1.0);
            const dotR = r * 1.01;

            dotPositions[i * 3]     = dotR * Math.sin(phi) * Math.cos(theta);
            dotPositions[i * 3 + 1] = dotR * Math.sin(phi) * Math.sin(theta);
            dotPositions[i * 3 + 2] = dotR * Math.cos(phi);
        }

        const dotGeo = new THREE.BufferGeometry();
        dotGeo.setAttribute('position', new THREE.BufferAttribute(dotPositions, 3));

        const dotMat = new THREE.PointsMaterial({
            color: isDarkMode ? 0x34d399 : 0x059669,
            size: isDarkMode ? 0.08 : 0.09,
            transparent: true,
            opacity: isDarkMode ? 0.40 : 0.52,
            blending: isDarkMode ? THREE.AdditiveBlending : THREE.NormalBlending,
            depthWrite: false
        });
        materialsList.push(dotMat);

        const matrixPoints = new THREE.Points(dotGeo, dotMat);
        globeGroup.add(matrixPoints);
    }

    function buildGlobalHubsAndArcs() {
        const r = CONFIG.globeRadius;

        const hubs = [
            { name: 'Lagos', lat: 6.5244, lon: 3.3792 },
            { name: 'London', lat: 51.5074, lon: -0.1278 },
            { name: 'New York', lat: 40.7128, lon: -74.0060 },
            { name: 'Tokyo', lat: 35.6762, lon: 139.6503 },
            { name: 'Nairobi', lat: -1.2921, lon: 36.8219 },
            { name: 'Dubai', lat: 25.2048, lon: 55.2708 },
            { name: 'Singapore', lat: 1.3521, lon: 103.8198 },
            { name: 'Johannesburg', lat: -26.2041, lon: 28.0473 },
            { name: 'São Paulo', lat: -23.5505, lon: -46.6333 }
        ];

        const nodeMat = new THREE.MeshBasicMaterial({
            color: isDarkMode ? 0x10b981 : 0x059669,
            transparent: true,
            opacity: isDarkMode ? 0.50 : 0.65
        });
        materialsList.push(nodeMat);

        const hubVectors = [];
        hubs.forEach(hub => {
            const vec = latLongToVector3(hub.lat, hub.lon, r * 1.01);
            hubVectors.push(vec);

            const hubPin = new THREE.Mesh(new THREE.SphereGeometry(isDarkMode ? 0.08 : 0.09, 8, 8), nodeMat);
            hubPin.position.copy(vec);
            globeGroup.add(hubPin);
        });

        const connections = [
            [0, 1], [0, 4], [0, 7], // Lagos -> London, Nairobi, J’burg
            [1, 2], [1, 5],         // London -> NY, Dubai
            [2, 8],                 // NY -> São Paulo
            [5, 6], [5, 3],         // Dubai -> Singapore, Tokyo
            [6, 3]                  // Singapore -> Tokyo
        ];

        const arcMat = new THREE.LineBasicMaterial({
            color: isDarkMode ? CONFIG.primaryColorDark : CONFIG.primaryColorLight,
            transparent: true,
            opacity: isDarkMode ? 0.25 : 0.38,
            blending: isDarkMode ? THREE.AdditiveBlending : THREE.NormalBlending,
            depthWrite: false
        });
        materialsList.push(arcMat);

        connections.forEach(([startIdx, endIdx], arcIndex) => {
            const startVec = hubVectors[startIdx];
            const endVec = hubVectors[endIdx];

            const midVec = new THREE.Vector3().addVectors(startVec, endVec).multiplyScalar(0.5);
            const dist = startVec.distanceTo(endVec);
            midVec.setLength(r + dist * 0.28);

            const curve = new THREE.QuadraticBezierCurve3(startVec, midVec, endVec);
            const points = curve.getPoints(28);
            const curveGeo = new THREE.BufferGeometry().setFromPoints(points);
            const curveMesh = new THREE.Line(curveGeo, arcMat);
            globeGroup.add(curveMesh);

            const pulseMesh = new THREE.Mesh(
                new THREE.SphereGeometry(0.055, 6, 6),
                new THREE.MeshBasicMaterial({
                    color: isDarkMode ? 0x06b6d4 : 0x0284c7,
                    transparent: true,
                    opacity: isDarkMode ? 0.55 : 0.75
                })
            );
            globeGroup.add(pulseMesh);

            arcCurves.push({
                curve: curve,
                pulse: pulseMesh,
                progress: (arcIndex * 0.15) % 1.0,
                speed: 0.004 + (arcIndex % 3) * 0.001
            });
        });
    }

    function buildOrbitalRings() {
        const r = CONFIG.globeRadius;

        const ringMat = new THREE.MeshBasicMaterial({
            color: isDarkMode ? CONFIG.secondaryColorDark : CONFIG.secondaryColorLight,
            transparent: true,
            opacity: isDarkMode ? 0.15 : 0.22,
            side: THREE.DoubleSide
        });
        materialsList.push(ringMat);

        const ring1Geo = new THREE.TorusGeometry(r * 1.25, 0.015, 10, 40);
        orbitalRing1 = new THREE.Mesh(ring1Geo, ringMat);
        orbitalRing1.rotation.x = Math.PI / 3;
        orbitalRing1.rotation.y = Math.PI / 6;
        globeGroup.add(orbitalRing1);

        const ring2Geo = new THREE.TorusGeometry(r * 1.36, 0.012, 10, 40);
        orbitalRing2 = new THREE.Mesh(ring2Geo, ringMat);
        orbitalRing2.rotation.x = -Math.PI / 4;
        orbitalRing2.rotation.y = -Math.PI / 3;
        globeGroup.add(orbitalRing2);
    }

    function buildAtmosphericParticles() {
        const count = isMobile ? 80 : 150;
        const positions = new Float32Array(count * 3);
        const r = CONFIG.globeRadius;

        for (let i = 0; i < count; i++) {
            const radius = r * 1.1 + Math.random() * 2.2;
            const theta = Math.random() * 2 * Math.PI;
            const phi = Math.acos(2 * Math.random() - 1);

            positions[i * 3]     = radius * Math.sin(phi) * Math.cos(theta);
            positions[i * 3 + 1] = radius * Math.sin(phi) * Math.sin(theta);
            positions[i * 3 + 2] = radius * Math.cos(phi);
        }

        const geo = new THREE.BufferGeometry();
        geo.setAttribute('position', new THREE.BufferAttribute(positions, 3));

        const mat = new THREE.PointsMaterial({
            color: isDarkMode ? 0x34d399 : 0x059669,
            size: isDarkMode ? 0.08 : 0.085,
            transparent: true,
            opacity: isDarkMode ? 0.35 : 0.42,
            blending: isDarkMode ? THREE.AdditiveBlending : THREE.NormalBlending,
            depthWrite: false
        });
        materialsList.push(mat);

        particleCloud = new THREE.Points(geo, mat);
        globeGroup.add(particleCloud);
    }

    function updateTheme() {
        if (!ambientLight || !pointLight) return;

        ambientLight.color.setHex(isDarkMode ? 0x022c22 : 0xd1fae5);
        ambientLight.intensity = isDarkMode ? 0.8 : 0.9;

        pointLight.color.setHex(isDarkMode ? CONFIG.primaryColorDark : CONFIG.primaryColorLight);
        pointLight.intensity = isDarkMode ? 1.4 : 1.8;

        cyanFillLight.color.setHex(isDarkMode ? CONFIG.secondaryColorDark : CONFIG.secondaryColorLight);
        cyanFillLight.intensity = isDarkMode ? 1.0 : 1.3;

        materialsList.forEach(mat => {
            if (mat instanceof THREE.MeshStandardMaterial) {
                mat.color.setHex(isDarkMode ? CONFIG.coreColorDark : CONFIG.coreColorLight);
                mat.emissive.setHex(isDarkMode ? CONFIG.primaryColorDark : CONFIG.primaryColorLight);
                mat.emissiveIntensity = isDarkMode ? 0.10 : 0.10;
                mat.opacity = isDarkMode ? 0.18 : 0.20;
            } else if (mat instanceof THREE.LineBasicMaterial) {
                mat.color.setHex(isDarkMode ? CONFIG.primaryColorDark : CONFIG.primaryColorLight);
                mat.opacity = isDarkMode ? 0.25 : 0.38;
                mat.blending = isDarkMode ? THREE.AdditiveBlending : THREE.NormalBlending;
            } else if (mat instanceof THREE.PointsMaterial) {
                mat.color.setHex(isDarkMode ? 0x34d399 : 0x059669);
                mat.opacity = isDarkMode ? 0.40 : 0.52;
                mat.blending = isDarkMode ? THREE.AdditiveBlending : THREE.NormalBlending;
            } else if (mat instanceof THREE.MeshBasicMaterial) {
                if (mat.wireframe) {
                    mat.color.setHex(isDarkMode ? CONFIG.wireColorDark : CONFIG.wireColorLight);
                    mat.opacity = isDarkMode ? 0.15 : 0.22;
                } else {
                    mat.opacity = isDarkMode ? 0.50 : 0.65;
                }
            }
        });
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
    }

    let clock = new THREE.Clock();

    function animate(time) {
        animationFrameId = requestAnimationFrame(animate);
        const elapsedTime = clock.getElapsedTime();

        if (!prefersReducedMotion) {
            mouse.x += (mouse.targetX - mouse.x) * 0.05;
            mouse.y += (mouse.targetY - mouse.y) * 0.05;

            if (globeGroup) {
                globeGroup.rotation.y = elapsedTime * 0.14 + mouse.x * 0.15;
                globeGroup.rotation.x = 0.12 + Math.sin(elapsedTime * 0.4) * 0.02 - mouse.y * 0.10;
            }

            if (orbitalRing1) orbitalRing1.rotation.z = -elapsedTime * 0.08;
            if (orbitalRing2) orbitalRing2.rotation.z = elapsedTime * 0.10;

            if (particleCloud) {
                particleCloud.rotation.y = elapsedTime * 0.06;
            }

            arcCurves.forEach(item => {
                item.progress += item.speed;
                if (item.progress > 1.0) item.progress = 0;
                const pt = item.curve.getPoint(item.progress);
                item.pulse.position.copy(pt);
            });
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
