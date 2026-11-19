// 把 three.js + 模型加载器 + 视角控制打成一个普通脚本：双击 html（file://）也能用，不需要本地服务器
import * as THREE from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { RoomEnvironment } from 'three/examples/jsm/environments/RoomEnvironment.js';
window.THREE = Object.assign({}, THREE, { GLTFLoader, OrbitControls, RoomEnvironment });
