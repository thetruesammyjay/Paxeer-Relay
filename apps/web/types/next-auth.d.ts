import "next-auth/jwt";

declare module "next-auth/jwt" {
  interface JWT {
    paxrelaySubject?: string;
    paxrelayIssuer?: string;
    paxrelayEmailVerified?: boolean;
  }
}
