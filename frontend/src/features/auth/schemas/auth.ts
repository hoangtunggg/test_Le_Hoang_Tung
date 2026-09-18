import { z } from "zod";

const PASSWORD_MIN_CHARACTERS = 6;
const PASSWORD_MAX_BYTES = 72;
const utf8Encoder = new TextEncoder();

const passwordSchema = z
  .string()
  .refine(
    (password) => Array.from(password).length >= PASSWORD_MIN_CHARACTERS,
    `Password must be at least ${PASSWORD_MIN_CHARACTERS} characters`,
  )
  .refine(
    (password) => utf8Encoder.encode(password).length <= PASSWORD_MAX_BYTES,
    `Password must be at most ${PASSWORD_MAX_BYTES} UTF-8 bytes`,
  );

export const loginSchema = z.object({
  email: z.string().email("Invalid email address"),
  password: passwordSchema,
});

export const registerSchema = z.object({
  email: z.string().email("Invalid email address"),
  password: passwordSchema,
  confirmPassword: passwordSchema,
}).refine((data) => data.password === data.confirmPassword, {
  message: "Passwords don't match",
  path: ["confirmPassword"],
});

export type LoginFormData = z.infer<typeof loginSchema>;
export type RegisterFormData = z.infer<typeof registerSchema>;
