// =====================================================================
// security.js — Middleware y utilidades de seguridad compartidas
// =====================================================================
// Centraliza lo que antes estaba duplicado (o ausente) en cada módulo de
// la API: el secreto JWT, el middleware que comprueba el token, y un
// saneador para los parámetros de filtro que llegan por query string.
//
// Antes de esta corrección:
//   - El secreto JWT estaba escrito en el código fuente (público en GitHub).
//   - Solo un endpoint (alcohol v2) comprobaba el token; el resto de
//     endpoints de escritura (v1 completo, literacy-rates y road-fatalities
//     en ambas versiones) no pedían ninguna autenticación.
//   - El login aceptaba credenciales fijas (admin/admin).
//   - Los filtros de los GET pasaban el valor de la query string
//     directamente a NeDB, permitiendo inyectar operadores (?campo[$ne]=...).
// =====================================================================

import jwt from "jsonwebtoken";

export const JWT_SECRET = process.env.JWT_SECRET;
if (!JWT_SECRET) {
    throw new Error(
        "Falta JWT_SECRET en el .env. Genera uno con:\n" +
        "  node -e \"console.log(require('crypto').randomBytes(48).toString('hex'))\"\n" +
        "y añádelo a .env (ver .env.example)."
    );
}

export const ADMIN_USER = process.env.ADMIN_USER;
export const ADMIN_PASSWORD = process.env.ADMIN_PASSWORD;
if (!ADMIN_USER || !ADMIN_PASSWORD) {
    throw new Error("Faltan ADMIN_USER / ADMIN_PASSWORD en el .env (ver .env.example).");
}

// --- Middleware de verificación de token ---
// Se aplica a todos los endpoints de escritura (POST/PUT/DELETE) de la API,
// en v1 y v2. Antes solo protegía un endpoint; ahora es uniforme en toda la API.
export function verifyToken(req, res, next) {
    const authHeader = req.headers["authorization"];

    if (!authHeader) {
        return res.status(403).json({ error: "No se ha proporcionado un token de autenticación." });
    }

    const token = authHeader.split(" ")[1];
    if (!token) {
        return res.status(403).json({ error: "Formato de token incorrecto." });
    }

    jwt.verify(token, JWT_SECRET, (err, decoded) => {
        if (err) {
            return res.status(401).json({ error: "Token inválido o caducado." });
        }
        req.user = decoded;
        next();
    });
}

// --- Saneador de parámetros de filtro ---
// Los filtros de los GET solo deben aceptar strings planos. Si Express
// (vía la librería `qs`) parsea el parámetro como un objeto (p. ej. por
// `?campo[$ne]=null`), esta función lo descarta en vez de dejarlo pasar
// a la consulta de NeDB como un operador.
export function stringFilter(value) {
    return typeof value === "string" ? value : undefined;
}
