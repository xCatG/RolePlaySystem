export interface AssetMetadata {
  character_id: string;
  display_name: string;
  default_pose: string;
  default_expression: string;
  sprite_config: {
    anchor_point: string;
    scale: number;
    position: { x: number; y: number };
  };
  animation_config: {
    blink_interval: [number, number];
    blink_duration: number;
    talking_frame_rate: number;
  };
}

export class AssetManager {
  private static instance: AssetManager;
  private imageCache: Map<string, HTMLImageElement> = new Map();
  private audioCache: Map<string, HTMLAudioElement> = new Map();
  private metadataCache: Map<string, AssetMetadata> = new Map();
  private loadingPromises: Map<string, Promise<any>> = new Map();
  
  private constructor() {}
  
  static getInstance(): AssetManager {
    if (!AssetManager.instance) {
      AssetManager.instance = new AssetManager();
    }
    return AssetManager.instance;
  }
  
  async loadImage(path: string): Promise<HTMLImageElement> {
    // Check cache first
    if (this.imageCache.has(path)) {
      return this.imageCache.get(path)!;
    }
    
    // Check if already loading
    if (this.loadingPromises.has(path)) {
      return this.loadingPromises.get(path) as Promise<HTMLImageElement>;
    }
    
    // Start loading
    const loadPromise = new Promise<HTMLImageElement>((resolve, reject) => {
      const img = new Image();
      img.onload = () => {
        this.imageCache.set(path, img);
        this.loadingPromises.delete(path);
        resolve(img);
      };
      img.onerror = () => {
        this.loadingPromises.delete(path);
        reject(new Error(`Failed to load image: ${path}`));
      };
      img.src = path;
    });
    
    this.loadingPromises.set(path, loadPromise);
    return loadPromise;
  }
  
  async loadAudio(path: string): Promise<HTMLAudioElement> {
    if (this.audioCache.has(path)) {
      return this.audioCache.get(path)!;
    }
    
    if (this.loadingPromises.has(path)) {
      return this.loadingPromises.get(path) as Promise<HTMLAudioElement>;
    }
    
    const loadPromise = new Promise<HTMLAudioElement>((resolve, reject) => {
      const audio = new Audio();
      audio.addEventListener('canplaythrough', () => {
        this.audioCache.set(path, audio);
        this.loadingPromises.delete(path);
        resolve(audio);
      }, { once: true });
      audio.addEventListener('error', () => {
        this.loadingPromises.delete(path);
        reject(new Error(`Failed to load audio: ${path}`));
      }, { once: true });
      audio.src = path;
      audio.load();
    });
    
    this.loadingPromises.set(path, loadPromise);
    return loadPromise;
  }
  
  async loadCharacterMetadata(characterId: string): Promise<AssetMetadata> {
    const cacheKey = `metadata_${characterId}`;
    if (this.metadataCache.has(cacheKey)) {
      return this.metadataCache.get(cacheKey)!;
    }
    
    const path = `/assets/characters/${characterId}/metadata.json`;
    const response = await fetch(path);
    if (!response.ok) {
      throw new Error(`Failed to load character metadata: ${characterId}`);
    }
    
    const metadata = await response.json();
    this.metadataCache.set(cacheKey, metadata);
    return metadata;
  }
  
  async preloadScene(sceneId: string): Promise<void> {
    // Preload common scene assets
    const backgroundPromises = [
      this.loadImage(`/assets/backgrounds/${sceneId}/default.jpg`),
      this.loadImage(`/assets/backgrounds/${sceneId}/morning.jpg`),
      this.loadImage(`/assets/backgrounds/${sceneId}/evening.jpg`),
      this.loadImage(`/assets/backgrounds/${sceneId}/night.jpg`)
    ].map(p => p.catch(() => null)); // Don't fail if some variants don't exist
    
    await Promise.all(backgroundPromises);
  }
  
  async preloadCharacter(characterId: string): Promise<void> {
    const metadata = await this.loadCharacterMetadata(characterId);
    
    // Preload default pose and expression
    const defaultSpritePath = `/assets/characters/${characterId}/poses/${metadata.default_pose}.png`;
    const defaultExpressionPath = `/assets/characters/${characterId}/expressions/${metadata.default_expression}.png`;
    
    await Promise.all([
      this.loadImage(defaultSpritePath),
      this.loadImage(defaultExpressionPath)
    ]);
  }
  
  async getCharacterSprite(
    characterId: string,
    pose: string,
    expression: string
  ): Promise<{ pose: HTMLImageElement; expression: HTMLImageElement }> {
    const posePath = `/assets/characters/${characterId}/poses/${pose}.png`;
    const expressionPath = `/assets/characters/${characterId}/expressions/${expression}.png`;
    
    const [poseImg, expressionImg] = await Promise.all([
      this.loadImage(posePath),
      this.loadImage(expressionPath)
    ]);
    
    return { pose: poseImg, expression: expressionImg };
  }
  
  getBackgroundPath(scenarioId: string, timeOfDay: string = 'default'): string {
    return `/assets/backgrounds/${scenarioId}/${timeOfDay}.jpg`;
  }
  
  clearCache(): void {
    this.imageCache.clear();
    this.audioCache.clear();
    this.metadataCache.clear();
    this.loadingPromises.clear();
  }
}