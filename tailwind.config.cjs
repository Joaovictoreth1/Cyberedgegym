module.exports = {
    content: ['./index.html'],
    theme: {
        extend: {
            colors: {
                void: '#000000',
                surface: '#050508',
                panel: '#0a0a0f',
                cyan: { 400: '#00f0ff', 500: '#00c3ff' },
                magenta: { 400: '#ff003c', 500: '#d90033' },
            },
            fontFamily: {
                sync: ['Syncopate', 'sans-serif'],
                sans: ['Manrope', 'sans-serif'],
                mono: ['JetBrains Mono', 'monospace'],
            },
            letterSpacing: {
                tighter: '-.04em',
                widest: '.25em',
                superwide: '.5em',
            },
        },
    },
};
