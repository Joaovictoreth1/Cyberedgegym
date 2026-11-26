/* global THREE, Tone */
'use strict';

function initAudio() {
    let audioInit = false;

    // Synth for hover events
    const synthHover = new Tone.PolySynth(Tone.Synth, {
        oscillator: { type: "sine" },
        envelope: { attack: 0.05, decay: 0.1, sustain: 0.1, release: 1 }
    }).toDestination();
    synthHover.volume.value = -15;

    // Synth for clicks
    const synthClick = new Tone.MembraneSynth().toDestination();
    synthClick.volume.value = -20;

    // Synth for typing in terminal
    const synthType = new Tone.NoiseSynth({
        noise: { type: "white" },
        envelope: { attack: 0.001, decay: 0.05, sustain: 0, release: 0.05 }
    }).toDestination();
    synthType.volume.value = -35;

    // Init Audio Context on first user interaction
    document.body.addEventListener('pointerdown', () => {
        Tone.start().then(() => { audioInit = true; }).catch(() => {});
    }, { once: true });

    // Bind Audio Events
    document.querySelectorAll('.sound-hover').forEach(el => {
        el.addEventListener('mouseenter', () => { if(audioInit) synthHover.triggerAttackRelease(["C5", "E5"], "32n"); });
    });
    document.querySelectorAll('.sound-click').forEach(el => {
        el.addEventListener('mousedown', () => { if(audioInit) synthClick.triggerAttackRelease("C2", "16n"); });
    });
    document.querySelectorAll('.sound-type input, .sound-type select').forEach(el => {
        el.addEventListener('input', () => { if(audioInit) synthType.triggerAttackRelease("64n"); });
    });
}

function initWebGL() {
    const container = document.getElementById('webgl-container');
    const scene = new THREE.Scene();
    scene.fog = new THREE.FogExp2(0x000000, 0.002);

    const camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 3000);
    camera.position.z = 1000;

    const renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true });
    renderer.setSize(window.innerWidth, window.innerHeight);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    container.appendChild(renderer.domElement);

    // Tunnel Geometry (Instanced points for performance)
    const particleCount = 6000;
    const geometry = new THREE.BufferGeometry();
    const positions = new Float32Array(particleCount * 3);
    const sizes = new Float32Array(particleCount);

    for(let i=0; i < particleCount; i++) {
        // Cylindrical placement
        const radius = 300 + Math.random() * 200; // Radius of tunnel
        const theta = Math.random() * Math.PI * 2; // Angle
        const z = (Math.random() - 0.5) * 4000; // Depth spread

        positions[i * 3] = radius * Math.cos(theta); // x
        positions[i * 3 + 1] = radius * Math.sin(theta); // y
        positions[i * 3 + 2] = z; // z

        sizes[i] = Math.random() * 2;
    }

    geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    geometry.setAttribute('size', new THREE.BufferAttribute(sizes, 1));

    // Custom Shader Material for glowing dots
    const material = new THREE.PointsMaterial({
        color: 0x00f0ff,
        size: 2,
        transparent: true,
        opacity: 0.8,
        blending: THREE.AdditiveBlending
    });

    const tunnel = new THREE.Points(geometry, material);
    scene.add(tunnel);

    // Core Node in the center
    const coreGeo = new THREE.IcosahedronGeometry(40, 2);
    const coreMat = new THREE.MeshBasicMaterial({ color: 0xff003c, wireframe: true, transparent: true, opacity: 0.5 });
    const core = new THREE.Mesh(coreGeo, coreMat);
    core.position.z = 200;
    scene.add(core);

    // Mouse & Scroll Tracking
    let mouseX = 0; let mouseY = 0;
    let targetX = 0; let targetY = 0;
    let scrollY = 0; let targetScrollZ = 1000;
    const windowHalfX = window.innerWidth / 2;
    const windowHalfY = window.innerHeight / 2;
    const appContent = document.getElementById('app-content');

    if(window.innerWidth > 768) {
        document.addEventListener('mousemove', (e) => {
            mouseX = (e.clientX - windowHalfX);
            mouseY = (e.clientY - windowHalfY);
        });
    }

    appContent.addEventListener('scroll', () => {
        scrollY = appContent.scrollTop;
        targetScrollZ = 1000 - (scrollY * 0.5); // Move forward as you scroll down
    });

    window.addEventListener('resize', () => {
        camera.aspect = window.innerWidth / window.innerHeight;
        camera.updateProjectionMatrix();
        renderer.setSize(window.innerWidth, window.innerHeight);
    });

    // Animation Loop
    const clock = new THREE.Clock();
    function animateThree() {
        requestAnimationFrame(animateThree);
        const time = clock.getElapsedTime();

        // Rotate Tunnel
        tunnel.rotation.z = time * 0.05;
        core.rotation.y = time * 0.2;
        core.rotation.x = time * 0.1;

        // Smooth Camera Parallax (Lerp)
        targetX = mouseX * 0.15;
        targetY = mouseY * 0.15;
        camera.position.x += (targetX - camera.position.x) * 0.05;
        camera.position.y += (-targetY - camera.position.y) * 0.05;

        // Camera Fly-through
        camera.position.z += (targetScrollZ - camera.position.z) * 0.05;

        camera.lookAt(0, 0, camera.position.z - 500); // Always look forward

        renderer.render(scene, camera);
    }
    animateThree();
}

function initPointerEffects() {
    const curDot = document.getElementById('cursor-dot');
    const curRing = document.getElementById('cursor-ring');
    let cx = window.innerWidth / 2, cy = window.innerHeight / 2;
    let rx = cx, ry = cy; // Ring positions for Lerp

    if (matchMedia('(min-width: 1024px) and (pointer: fine)').matches) {
        document.body.classList.add('custom-cursor');
        document.addEventListener('mousemove', (e) => {
            cx = e.clientX; cy = e.clientY;
            curDot.style.transform = `translate(calc(${cx}px - 50%), calc(${cy}px - 50%))`;
        });

        function renderCursor() {
            // Lerp formula for smooth follow
            rx += (cx - rx) * 0.15;
            ry += (cy - ry) * 0.15;
            curRing.style.transform = `translate(calc(${rx}px - 50%), calc(${ry}px - 50%))`;
            requestAnimationFrame(renderCursor);
        }
        requestAnimationFrame(renderCursor);

        // Magnetic Logic
        document.querySelectorAll('.magnetic').forEach(el => {
            el.addEventListener('mousemove', (e) => {
                const rect = el.getBoundingClientRect();
                const elCx = rect.left + rect.width / 2;
                const elCy = rect.top + rect.height / 2;
                // Move button
                el.style.transform = `translate(${(e.clientX - elCx) * 0.2}px, ${(e.clientY - elCy) * 0.2}px)`;

                // Expand Cursor
                curRing.style.width = '60px'; curRing.style.height = '60px';
                curRing.style.backgroundColor = 'rgba(0, 240, 255, 0.1)';
            });
            el.addEventListener('mouseleave', () => {
                el.style.transform = 'translate(0px, 0px)';
                el.style.transition = 'transform 0.5s cubic-bezier(0.19, 1, 0.22, 1)';
                curRing.style.width = '40px'; curRing.style.height = '40px';
                curRing.style.backgroundColor = 'transparent';
                setTimeout(() => { el.style.transition = ''; }, 500);
            });
        });
    }

    document.querySelectorAll('.spotlight-card').forEach(card => {
        const inner = card.querySelector('.spotlight-inner');

        card.addEventListener('mousemove', e => {
            const rect = card.getBoundingClientRect();
            const x = e.clientX - rect.left;
            const y = e.clientY - rect.top;

            // Spotlight glow
            card.style.setProperty('--mouse-x', `${x}px`);
            card.style.setProperty('--mouse-y', `${y}px`);

            // 3D Tilt Logic
            if(card.classList.contains('tilt-card')) {
                const centerX = rect.width / 2;
                const centerY = rect.height / 2;
                const rotateX = ((y - centerY) / centerY) * -10; // Max 10 deg
                const rotateY = ((x - centerX) / centerX) * 10;

                inner.style.transform = `perspective(1000px) rotateX(${rotateX}deg) rotateY(${rotateY}deg) scale3d(1.02, 1.02, 1.02)`;
            }
        });

        card.addEventListener('mouseleave', () => {
            if(card.classList.contains('tilt-card')) {
                inner.style.transform = `perspective(1000px) rotateX(0deg) rotateY(0deg) scale3d(1, 1, 1)`;
                inner.style.transition = 'transform 0.5s cubic-bezier(0.25, 1, 0.5, 1)';
                setTimeout(() => { inner.style.transition = 'transform 0.1s ease-out'; }, 500);
            }
        });
    });
}

function initScrollEffects() {
    if (!('IntersectionObserver' in window)) return;
    const appContent = document.getElementById('app-content');
    // Reveal elements
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('active');
                observer.unobserve(entry.target);
            }
        });
    }, { threshold: 0.1, root: appContent });
    document.querySelectorAll('.reveal').forEach(el => observer.observe(el));
    appContent.classList.add('motion-enabled');

    // Scramble Text Effect
    const chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!<>-_\\/[]{}—=+*^?#_";
    const scrambleObs = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const el = entry.target;
                const original = el.getAttribute('data-text');
                let iter = 0;
                clearInterval(el.dataset.interval);

                el.dataset.interval = setInterval(() => {
                    el.innerText = original.split("").map((l, i) => {
                        if(i < iter) return original[i];
                        if(l === " " || l === ".") return l;
                        return chars[Math.floor(Math.random() * chars.length)];
                    }).join("");

                    if(iter >= original.length) clearInterval(el.dataset.interval);
                    iter += 1/3;
                }, 30);
                scrambleObs.unobserve(el);
            }
        });
    }, { threshold: 0.5, root: appContent });
    document.querySelectorAll('.scramble-text').forEach(el => scrambleObs.observe(el));
}

if (!matchMedia('(prefers-reduced-motion: reduce)').matches) {
    for (const initialize of [initScrollEffects, initPointerEffects, initWebGL, initAudio]) {
        try {
            initialize();
        } catch {
            // Optional effects must not affect the contact flow.
        }
    }
}
