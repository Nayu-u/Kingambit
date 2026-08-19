(function() {
    const canvas = document.getElementById('antigravityCanvas');
    if (!canvas) return;

    const renderer = new THREE.WebGLRenderer({
        canvas: canvas,
        alpha: true,
        antialias: false,
        powerPreference: "high-performance"
    });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.2));
    renderer.setSize(window.innerWidth, window.innerHeight);

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(55, window.innerWidth / window.innerHeight, 1, 1000);
    camera.position.z = 220;

    const count = 1200;
    const geometry = new THREE.BufferGeometry();
    const positions = new Float32Array(count * 3);
    const sizes = new Float32Array(count);
    const randoms = new Float32Array(count * 3);
    const depths = new Float32Array(count);
    const colorIds = new Float32Array(count);

    for (let i = 0; i < count; i++) {
        const x = (Math.random() - 0.5) * 550;
        const y = (Math.random() - 0.5) * 550;
        const z = (Math.random() - 0.5) * 350;

        positions[i * 3] = x;
        positions[i * 3 + 1] = y;
        positions[i * 3 + 2] = z;

        sizes[i] = 2.0 + Math.random() * 4.0;

        randoms[i * 3] = Math.random();
        randoms[i * 3 + 1] = Math.random();
        randoms[i * 3 + 2] = Math.random();

        depths[i] = Math.random();
        colorIds[i] = Math.floor(Math.random() * 3);
    }

    geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    geometry.setAttribute('aSize', new THREE.BufferAttribute(sizes, 1));
    geometry.setAttribute('aRandom', new THREE.BufferAttribute(randoms, 3));
    geometry.setAttribute('aDepth', new THREE.BufferAttribute(depths, 1));
    geometry.setAttribute('aColorId', new THREE.BufferAttribute(colorIds, 1));

    const vertexShader = `
        uniform float uTime;
        uniform vec2 uMouse;
        uniform float uMouseActive;
        uniform vec3 uMouse3D;

        attribute float aSize;
        attribute vec3 aRandom;
        attribute float aDepth;
        attribute float aColorId;

        varying float vDepth;
        varying float vColorId;
        varying vec3 vPosition;

        void main() {
            vec3 pos = position;

            float t = uTime * 0.12;
            pos.x += sin(t + aRandom.x * 6.28) * 8.0 * aDepth + cos(t * 0.6 + aRandom.y * 3.14) * 4.0 * aDepth;
            pos.y += cos(t * 0.8 + aRandom.y * 6.28) * 8.0 * aDepth + sin(t * 0.4 + aRandom.z * 3.14) * 4.0 * aDepth;
            pos.z += sin(t * 1.0 + aRandom.z * 6.28) * 8.0 * aDepth + cos(t * 0.2 + aRandom.x * 3.14) * 4.0 * aDepth;

            if (uMouseActive > 0.5) {
                vec3 dir = pos - uMouse3D;
                float dist = length(dir);
                if (dist < 160.0) {
                    float force = pow((160.0 - dist) / 160.0, 1.5) * aDepth;
                    pos += normalize(dir) * force * 55.0;
                }
            }

            vPosition = pos;
            vDepth = aDepth;
            vColorId = aColorId;

            vec4 mvPosition = modelViewMatrix * vec4(pos, 1.0);
            gl_Position = projectionMatrix * mvPosition;
            gl_PointSize = aSize * (220.0 / -mvPosition.z);
        }
    `;

    const fragmentShader = `
        uniform float uTime;
        varying float vDepth;
        varying float vColorId;
        varying vec3 vPosition;

        void main() {
            float dist = length(gl_PointCoord - vec2(0.5));
            float alpha = smoothstep(0.5, 0.02, dist);
            if (alpha < 0.01) discard;

            vec3 blue = vec3(0.0, 0.94, 1.0);
            vec3 purple = vec3(0.74, 0.0, 0.87);
            vec3 emerald = vec3(0.1, 1.0, 0.5);
            vec3 white = vec3(1.0, 1.0, 1.0);

            float id = floor(vColorId + 0.5);
            vec3 baseColor;
            if (id == 1.0) baseColor = purple;
            else if (id == 2.0) baseColor = emerald;
            else baseColor = blue;

            float wave = sin(vPosition.x * 0.0035 + uTime * 0.28) * 0.5 + 0.5;
            vec3 color = mix(baseColor, white, wave * 0.25 * vDepth);

            float glow = smoothstep(0.5, 0.0, dist);
            color = mix(color, white, glow * 0.3 * vDepth);

            float finalAlpha = alpha * (0.6 + 0.4 * vDepth) * 0.75;
            gl_FragColor = vec4(color, finalAlpha);
        }
    `;

    const material = new THREE.ShaderMaterial({
        vertexShader: vertexShader,
        fragmentShader: fragmentShader,
        uniforms: {
            uTime: { value: 0 },
            uMouse: { value: new THREE.Vector2(-1000, -1000) },
            uMouseActive: { value: 0 },
            uMouse3D: { value: new THREE.Vector3(0, 0, 0) }
        },
        transparent: true,
        depthWrite: false,
        blending: THREE.AdditiveBlending
    });

    const points = new THREE.Points(geometry, material);
    scene.add(points);

    const mouse = { active: 0, targetX: 0, targetY: 0, currentX: 0, currentY: 0 };
    const plane = new THREE.Plane(new THREE.Vector3(0, 0, 1), 0);
    const raycaster = new THREE.Raycaster();

    let lastMoveTime = 0;

    window.addEventListener('mousemove', (e) => {
        const now = performance.now();
        if (now - lastMoveTime < 16) return;
        lastMoveTime = now;

        mouse.targetX = (e.clientX / window.innerWidth) * 2 - 1;
        mouse.targetY = -(e.clientY / window.innerHeight) * 2 + 1;
        mouse.active = 1;

        raycaster.setFromCamera(new THREE.Vector2(mouse.targetX, mouse.targetY), camera);
        const intersectPoint = new THREE.Vector3();
        raycaster.ray.intersectPlane(plane, intersectPoint);
        material.uniforms.uMouse3D.value.copy(intersectPoint);
    });

    window.addEventListener('mouseleave', () => {
        mouse.active = 0;
    });

    window.addEventListener('resize', () => {
        camera.aspect = window.innerWidth / window.innerHeight;
        camera.updateProjectionMatrix();
        renderer.setSize(window.innerWidth, window.innerHeight);
        renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.2));
    });

    const clock = new THREE.Clock();
    let animationId = null;

    function animate() {
        const time = clock.getElapsedTime();
        material.uniforms.uTime.value = time;

        mouse.currentX += (mouse.targetX - mouse.currentX) * 0.03;
        mouse.currentY += (mouse.targetY - mouse.currentY) * 0.03;

        if (mouse.active) {
            material.uniforms.uMouseActive.value = 1.0;
            camera.position.x = mouse.currentX * 18.0;
            camera.position.y = mouse.currentY * 18.0;
            camera.lookAt(0, 0, 0);
        } else {
            material.uniforms.uMouseActive.value = 0.0;
            camera.position.x += (0 - camera.position.x) * 0.015;
            camera.position.y += (0 - camera.position.y) * 0.015;
            camera.lookAt(0, 0, 0);
        }

        points.rotation.y = time * 0.0009;
        points.rotation.x = time * 0.0004;

        renderer.render(scene, camera);
        animationId = requestAnimationFrame(animate);
    }

    const observer = new MutationObserver(() => {
        if (document.body.classList.contains('noturno')) {
            canvas.style.display = 'block';
            if (!animationId) animate();
        } else {
            canvas.style.display = 'none';
            if (animationId) {
                cancelAnimationFrame(animationId);
                animationId = null;
            }
        }
    });
    observer.observe(document.body, { attributes: true, attributeFilter: ['class'] });

    if (document.body.classList.contains('noturno')) {
        canvas.style.display = 'block';
        animate();
    }
})();