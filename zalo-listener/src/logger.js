/**
 * JAMA Zalo Listener -- Winston Logger
 *
 * Structured JSON logging for production; human-readable colour console for dev.
 * Every log entry includes a timestamp and a service tag.
 */

import winston from "winston";
import { config } from "./config.js";

const isDev = config.logLevel === "debug";

export const logger = winston.createLogger({
  level: config.logLevel,
  defaultMeta: { service: "zalo-listener" },
  format: winston.format.combine(
    winston.format.timestamp(),
    winston.format.errors({ stack: true }),
  ),
  transports: [
    new winston.transports.Console({
      format: isDev
        ? winston.format.combine(
            winston.format.colorize(),
            winston.format.printf(({ timestamp, level, message, ...meta }) => {
              const extra = Object.keys(meta).length > 1
                ? " " + JSON.stringify(meta)
                : "";
              return `${timestamp} [${level}] ${message}${extra}`;
            }),
          )
        : winston.format.json(),
    }),
  ],
});
