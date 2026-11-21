# CyberEdge Gym

> Infraestrutura Edge Computing para Academias — Latência Zero.

[![Deploy Status](https://img.shields.io/badge/status-live-00f0ff?style=flat-square)](https://joaovictoreth1.github.io/Cyberedgegym/)
[![License](https://img.shields.io/badge/license-MIT-magenta?style=flat-square)](LICENSE)

---

## Sobre o Projeto

**CyberEdge Gym** é uma plataforma de infraestrutura de TI especializada para academias, oferecendo:
- 🌐 Redes Edge de alta performance (latência < 10ms)
- 🔒 Destravamento de catraca com biometria local
- 📱 Desenvolvimento de aplicativos White Label
- 🛠️ Suporte técnico 24/7

## Estrutura do Projeto

```
Cyberedgegym/
├── index.html          # Landing page (SPA, HTML/CSS/JS puro)
├── backend/            # API REST (FastAPI Python) [em desenvolvimento]
│   ├── main.py
│   ├── requirements.txt
│   └── .env.example
├── .github/
│   └── workflows/
│       └── ci.yml      # GitHub Actions CI
├── .gitignore
└── README.md
```

## Rodando Localmente (Frontend)

Não requer nenhuma dependência — abra diretamente no navegador:

```bash
# Clone o repositório
git clone https://github.com/Joaovictoreth1/Cyberedgegym.git
cd Cyberedgegym

# Abra no navegador
# Duplo clique em index.html, ou:
npx serve .   # Se tiver Node.js instalado
```

## Rodando o Backend (em breve)

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env
# edite .env com suas credenciais
uvicorn main:app --reload
```

A API ficará disponível em: `http://localhost:8000`  
Documentação automática: `http://localhost:8000/docs`

## Deploy

| Componente | Plataforma | URL |
|-----------|-----------|-----|
| Frontend | GitHub Pages | https://joaovictoreth1.github.io/Cyberedgegym/ |
| Backend | Railway / Render | em breve |

## Planos de Serviço

| Tier | Alunos | Preço |
|------|--------|-------|
| START | Até 500 | R$ 1.000 / trimestre |
| PRO | Até 1.000 | R$ 2.000 / trimestre |
| ENTERPRISE | 1.000+ | R$ 3.000 / bimestre |

## Contato

Para parcerias e contratação de serviços:
- 📧 contato@cyberedgegym.com.br
- 💼 https://github.com/Joaovictoreth1

---

Projeto desenvolvido para o **Senac Empreenda 2026**  
© 2026 CyberEdge Gym. Todos os direitos reservados.
