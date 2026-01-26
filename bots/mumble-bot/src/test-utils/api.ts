import SuperTest from "supertest";
import { RestApi } from "../server/api/rest-api";

export const api = (): SuperTest.SuperTest<SuperTest.Test> => SuperTest(tsdi.get(RestApi).app);
