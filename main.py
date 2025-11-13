import pygame, math, sys, random, heapq
pygame.init()
info = pygame.display.Info()
WIDTH, HEIGHT = info.current_w, info.current_h
screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.FULLSCREEN)
pygame.display.set_caption("Maze Horror Game")
clock = pygame.time.Clock()
MAP_W, MAP_H = 31, 31

# --- Sounds ---
pygame.mixer.init()
footstep_sound = pygame.mixer.Sound("maze/step.mp3")
key_pickup_sound = pygame.mixer.Sound("maze/key_pickup.mp3")
jumpscare_sound = pygame.mixer.Sound("maze/jumpscare.mp3")
vent_sound = pygame.mixer.Sound("maze/vent.mp3")
ambience_sound = pygame.mixer.Sound("maze/ambient.mp3")
ambience_sound.set_volume(0.3)
ambience_sound.play(-1)

# --- Maze Generation ---
def generate_maze(w, h):
    maze = [[1]*w for _ in range(h)]
    stack = [(1,1)]
    maze[1][1] = 0
    directions = [(0,2),(0,-2),(2,0),(-2,0)]
    while stack:
        x,y = stack[-1]
        neighbors = []
        for dx,dy in directions:
            nx, ny = x+dx, y+dy
            if 1 <= nx < w-1 and 1 <= ny < h-1:
                if maze[ny][nx] == 1:
                    neighbors.append((nx,ny))
        if neighbors:
            nx,ny = random.choice(neighbors)
            maze[ny][nx] = 0
            maze[y + (ny-y)//2][x + (nx-x)//2] = 0
            stack.append((nx,ny))
        else:
            stack.pop()
    maze[h-2][w-2] = 2
    for _ in range(10):
        x = random.randrange(1,w-1,2)
        y = random.randrange(1,h-1,2)
        maze[y][x] = 0
    return maze

maze_map = generate_maze(MAP_W, MAP_H)

# --- Player ---
px, py, pa = 1.5, 1.5, 0
FOV, DEPTH, SPEED, ROT_SPEED = math.pi/3, 12, 0.04, 0.05
WALL_COLOR, FLOOR_COLOR, CEILING_COLOR, EXIT_COLOR = (180,180,180),(120,120,120),(60,60,60),(50,50,50)
AMBIENT_BRIGHTNESS, flashlight_on = 120, True

# --- Items ---
world_items=[]
free_cells = [(x+0.5,y+0.5) for y in range(MAP_H) for x in range(MAP_W) if maze_map[y][x]==0]
random.shuffle(free_cells)
key_images = [pygame.image.load(f"maze/key.png").convert_alpha() for i in range(5)]
for i in range(5):
    world_items.append({"x":free_cells[i][0],"y":free_cells[i][1],"type":"key","img":key_images[i],"float_offset":random.uniform(0,2*math.pi)})
inventory=[]; required_keys=5; exit_unlocked=False
item_colors={"key":(255,215,0)}
font = pygame.font.Font(pygame.font.match_font('couriernew', bold=True), 24)
win_font = pygame.font.Font(pygame.font.match_font('arial', bold=True), 72)
message, message_timer = "",0

# --- Lockers / hiding ---
lockers=[]
wall_positions=[(2.5,2.5),(MAP_W-3.5,2.5),(2.5,MAP_H-3.5),(MAP_W-3.5,MAP_H-3.5)]
for pos in wall_positions: lockers.append({"x":pos[0],"y":pos[1],"occupied":False})
locker_color_front=(90,120,150); locker_color_side=(60,80,100)
hiding=False

# --- Vents ---
vent_img = pygame.image.load("maze/vent.png").convert_alpha()
vents = []
for i in range(5):
    vx, vy = free_cells.pop()
    vents.append({"x":vx,"y":vy})
vent_cooldown = 0
VENT_DEBOUNCE = 60

# --- Vent Fade ---
vent_fade = False
vent_fade_alpha = 0
VENT_FADE_SPEED = 15
vent_target = None
vent_fade_phase = "fade_out"

# --- Enemy ---
enemy_img = pygame.image.load("maze/myers.png").convert_alpha()
enemy={"x":MAP_W-2.5,"y":MAP_H-2.5,"path":[],"speed":0.001,"seen":False}
enemy_cooldown = 0

# --- Pathfinding ---
def heuristic(a,b): return abs(a[0]-b[0])+abs(a[1]-b[1])
def astar(start,goal):
    if maze_map[goal[1]][goal[0]]==1: return []
    frontier = []
    heapq.heappush(frontier,(0,start))
    came_from={start:None}; cost_so_far={start:0}
    while frontier:
        _,current=heapq.heappop(frontier)
        if current==goal: break
        for dx,dy in [(1,0),(-1,0),(0,1),(0,-1)]:
            nx,ny=current[0]+dx,current[1]+dy
            if 0<=nx<MAP_W and 0<=ny<MAP_H and maze_map[ny][nx]!=1:
                new_cost=cost_so_far[current]+1
                if (nx,ny) not in cost_so_far or new_cost<cost_so_far[(nx,ny)]:
                    cost_so_far[(nx,ny)]=new_cost
                    priority=new_cost+heuristic(goal,(nx,ny))
                    heapq.heappush(frontier,(priority,(nx,ny)))
                    came_from[(nx,ny)]=current
    path=[]
    node=goal
    while node in came_from and node!=start:
        path.append(node)
        node=came_from[node]
    return path[::-1]

def has_line_of_sight(tx,ty):
    steps=int(max(abs(tx-px),abs(ty-py))*10)
    for i in range(steps):
        x=px+(tx-px)*(i/steps)
        y=py+(ty-py)*(i/steps)
        if maze_map[int(y)][int(x)]==1: return False
    return True

# --- Controls Page ---
def show_controls():
    controls = [
        ("Maze Horror Game Controls:", (255, 255, 255)),
        ("W/S", (255, 0, 0)), (": Move forward/backward", (255, 255, 255)),
        ("A/D", (255, 0, 0)), (": Rotate left/right", (255, 255, 255)),
        ("F", (255, 0, 0)), (": Toggle flashlight", (255, 255, 255)),
        ("M", (255, 0, 0)), (": Toggle minimap", (255, 255, 255)),
        ("E", (255, 0, 0)), (": Use vent", (255, 255, 255)),
        ("", (255, 255, 255)),
        ("Collect 5 keys", (255, 0, 0)), (" to unlock the exit.", (255, 255, 255)),
        ("Use vents", (255, 0, 0)), (" to avoid the enemy.", (255, 255, 255)),
        ("", (255, 255, 255)),
        ("Press any key to start...", (255, 255, 255))
    ]
    
    screen.fill((0, 0, 0))
    y = 50
    
    for item in controls:
        text, color = item
        rendered_text = font.render(text, True, color)
        screen.blit(rendered_text, (WIDTH//2 - rendered_text.get_width()//2, y))
        y += 40
    
    pygame.display.flip()
    
    waiting = True
    while waiting:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if event.type == pygame.KEYDOWN:
                waiting = False

show_controls()


# --- Rendering ---
def cast_rays():
    for col in range(WIDTH):
        ray_angle = pa-FOV/2 + (col/WIDTH)*FOV
        eye_x, eye_y = math.sin(ray_angle), math.cos(ray_angle)
        dist, hit, hit_type = 0, False, 1
        while not hit and dist<DEPTH:
            dist+=0.05
            tx, ty = int(px+eye_x*dist), int(py+eye_y*dist)
            if tx<0 or tx>=MAP_W or ty<0 or ty>=MAP_H:
                hit=True; dist=DEPTH
            elif maze_map[ty][tx]>0:
                hit=True; hit_type=maze_map[ty][tx]
        wall_height=int(HEIGHT/dist)
        ceiling=HEIGHT//2 - wall_height//2
        floor=HEIGHT//2 + wall_height//2
        shade=int(max(min(255/(1+dist**2*0.1),255),0))
        color=EXIT_COLOR if hit_type==2 else tuple(int(c*shade/255) for c in WALL_COLOR)
        pygame.draw.line(screen,color,(col,ceiling),(col,floor))
        pygame.draw.line(screen,CEILING_COLOR,(col,0),(col,ceiling))
        pygame.draw.line(screen,FLOOR_COLOR,(col,floor),(col,HEIGHT))

def draw_items():
    time = pygame.time.get_ticks() / 500
    for item in world_items:
        dx, dy = item["x"]-px, item["y"]-py
        dist = math.hypot(dx,dy)
        angle = math.atan2(dx,dy)-pa
        if angle<-math.pi: angle+=2*math.pi
        if angle>math.pi: angle-=2*math.pi
        if abs(angle)>FOV/2 or dist>DEPTH or dist<0.2: continue
        if not has_line_of_sight(item["x"],item["y"]): continue
        # Floating effect
        float_y = math.sin(time + item["float_offset"])*0.2
        size=int(350/(dist+0.001))
        x=int((WIDTH/2)+(angle/(FOV/2))*(WIDTH/2))
        y=HEIGHT//2 + int(float_y*100)
        sprite=pygame.transform.scale(item["img"],(size,size))
        rect=sprite.get_rect(center=(x,y))
        screen.blit(sprite,rect)

def draw_enemy():
    dx, dy = enemy["x"]-px, enemy["y"]-py
    dist = math.hypot(dx,dy)
    if dist>DEPTH: return
    angle = math.atan2(dx,dy)-pa
    if angle<-math.pi: angle+=2*math.pi
    if angle>math.pi: angle-=2*math.pi
    if abs(angle)>FOV/2 or not has_line_of_sight(enemy["x"],enemy["y"]): return
    size=int(600/(dist+0.001))
    x=int((WIDTH/2)+(angle/(FOV/2))*(WIDTH/2))
    y=HEIGHT//2
    sprite=pygame.transform.scale(enemy_img,(size,size))
    rect=sprite.get_rect(center=(x,y))
    screen.blit(sprite,rect)

# --- Vent Rendering (fixed size) ---
def draw_vents_3d():
    FIXED_SIZE = 60
    for vent in vents:
        dx, dy = vent["x"]-px, vent["y"]-py
        dist = math.hypot(dx,dy)
        if dist>DEPTH: continue
        angle = math.atan2(dx,dy)-pa
        if angle<-math.pi: angle+=2*math.pi
        if angle>math.pi: angle-=2*math.pi
        if abs(angle)>FOV/2 or not has_line_of_sight(vent["x"],vent["y"]): continue
        x = int((WIDTH/2) + (angle/(FOV/2))*(WIDTH/2))
        y = HEIGHT//2
        sprite = pygame.transform.scale(vent_img,(FIXED_SIZE,FIXED_SIZE))
        rect = sprite.get_rect(center=(x,y))
        screen.blit(sprite,rect)

def draw_flashlight():
    dark=pygame.Surface((WIDTH,HEIGHT),pygame.SRCALPHA)
    dark.fill((0,0,0,255-AMBIENT_BRIGHTNESS))
    if flashlight_on:
        mask=pygame.Surface((WIDTH,HEIGHT),pygame.SRCALPHA)
        cone_len, cone_w = 400, 250
        cx,cy = WIDTH//2, HEIGHT//2
        ex,ey = cx+math.sin(pa)*cone_len, cy-math.cos(pa)*cone_len
        pygame.draw.polygon(mask,(0,0,0,0),[
            (cx-math.cos(pa)*cone_w//2, cy-math.sin(pa)*cone_w//2),
            (cx+math.cos(pa)*cone_w//2, cy+math.sin(pa)*cone_w//2),
            (ex,ey)
        ])
        dark.blit(mask,(0,0),special_flags=pygame.BLEND_RGBA_SUB)
    screen.blit(dark,(0,0))

def draw_message():
    global message_timer
    if message and message_timer>0:
        text=font.render(message,True,(255,255,255))
        screen.blit(text,text.get_rect(center=(WIDTH//2,40)))
        message_timer-=1

# --- Item pickup ---
def pickup_items():
    global exit_unlocked,message,message_timer
    for item in world_items[:]:
        if math.hypot(item["x"]-px,item["y"]-py)<0.5:
            world_items.remove(item)
            inventory.append(item["type"])
            message=f"Picked up {item['type']}!"
            message_timer=120
            key_pickup_sound.play()
    if inventory.count("key")>=required_keys:
        exit_unlocked=True
        message="Exit unlocked!"
        message_timer=180

# --- Enemy AI ---
def update_enemy(dt):
    global enemy_cooldown
    if hiding: return
    ex,ey = enemy["x"], enemy["y"]
    player_tile = (int(px),int(py))
    enemy_tile = (int(ex),int(ey))
    if has_line_of_sight(px,py): enemy["seen"]=True
    if enemy_cooldown<=0:
        if enemy["seen"]: enemy["path"]=astar(enemy_tile,player_tile); enemy_cooldown=30
        elif not enemy["path"]: target=random.choice(free_cells); enemy["path"]=astar(enemy_tile,(int(target[0]),int(target[1]))); enemy_cooldown=60
    if enemy_cooldown>0: enemy_cooldown-=1
    if enemy["path"]:
        nx,ny=enemy["path"][0]
        dx,dy = nx+0.5-ex, ny+0.5-ey
        dist=math.hypot(dx,dy)
        if dist<0.1: enemy["path"].pop(0)
        else: enemy["x"]+=dx/dist*enemy["speed"]*dt; enemy["y"]+=dy/dist*enemy["speed"]*dt

# --- Exit ---
def check_exit():
    for y in range(MAP_H):
        for x in range(MAP_W):
            if maze_map[y][x]==2 and int(px)==x and int(py)==y and exit_unlocked: return True
    return False

def draw_win_screen():
    overlay=pygame.Surface((WIDTH,HEIGHT)); overlay.fill((0,0,0))
    screen.blit(overlay,(0,0))
    t=win_font.render("YOU WIN!",True,(255,255,0))
    screen.blit(t,t.get_rect(center=(WIDTH//2,HEIGHT//2)))

def draw_loss_screen():
    overlay=pygame.Surface((WIDTH,HEIGHT)); overlay.fill((0,0,0))
    screen.blit(overlay,(0,0))
    t=win_font.render("YOU DIED",True,(255,0,0))
    screen.blit(t,t.get_rect(center=(WIDTH//2,HEIGHT//2)))
    jumpscare_sound.play()

# --- Minimap ---
def draw_minimap():
    size=150
    surf=pygame.Surface((MAP_W*5,MAP_H*5),pygame.SRCALPHA)
    surf.fill((30,30,30,180))
    for y in range(MAP_H):
        for x in range(MAP_W):
            if maze_map[y][x]==1: pygame.draw.rect(surf,(80,80,80),(x*5,y*5,5,5))
            elif maze_map[y][x]==2: pygame.draw.rect(surf,(0,255,0),(x*5,y*5,5,5))
    for item in world_items: pygame.draw.rect(surf,item_colors[item["type"]],(int(item["x"]*5)-2,int(item["y"]*5)-2,4,4))
    for locker in lockers: pygame.draw.rect(surf,(150,50,50),(int(locker["x"]*5)-2,int(locker["y"]*5)-2,4,4))
    for vent in vents: surf.blit(pygame.transform.scale(vent_img,(5,5)),(int(vent["x"]*5),int(vent["y"]*5)))
    pygame.draw.rect(surf,(255,0,0),(int(enemy["x"]*5)-2,int(enemy["y"]*5)-2,4,4))
    pygame.draw.rect(surf,(0,0,255),(int(px*5)-2,int(py*5)-2,4,4))
    screen.blit(surf,(WIDTH-size-10,10))

# --- Hiding ---
def check_hiding():
    global hiding
    hiding=False
    for locker in lockers:
        if math.hypot(locker["x"]-px,locker["y"]-py)<0.5: hiding=True

# --- Vent Teleport ---
def check_vent(keys):
    global vent_fade, vent_target, vent_cooldown, vent_fade_alpha, px, py, message, message_timer, vent_fade_phase
    if vent_cooldown>0 or vent_fade: return
    if not keys[pygame.K_e]: return
    for vent in vents:
        if math.hypot(vent["x"]-px, vent["y"]-py)<0.5:
            vent_target = random.choice([v for v in vents if v!=vent])
            vent_fade = True
            vent_fade_alpha = 0
            vent_fade_phase = "fade_out"
            vent_sound.play()
            break

def update_vent_fade():
    global vent_fade, vent_fade_alpha, vent_fade_phase, px, py, vent_cooldown, message, message_timer
    if vent_fade:
        fade_surf = pygame.Surface((WIDTH, HEIGHT))
        fade_surf.fill((0,0,0))
        if vent_fade_phase == "fade_out":
            vent_fade_alpha += VENT_FADE_SPEED
            if vent_fade_alpha >= 255:
                vent_fade_alpha = 255
                px, py = vent_target["x"], vent_target["y"]
                message = "Teleported through vent!"
                message_timer = 120
                vent_cooldown = VENT_DEBOUNCE
                vent_fade_phase = "fade_in"
        elif vent_fade_phase == "fade_in":
            vent_fade_alpha -= VENT_FADE_SPEED
            if vent_fade_alpha <= 0:
                vent_fade_alpha = 0
                vent_fade = False
                vent_fade_phase = "fade_out"
        fade_surf.set_alpha(vent_fade_alpha)
        screen.blit(fade_surf, (0, 0))

# --- Main Loop ---
minimap_on = True
won = lost = False
footstep_timer = 0

while True:
    dt = clock.tick(60)
    if vent_cooldown > 0:
        vent_cooldown -= 1

    # --- Event handling ---
    for e in pygame.event.get():
        if e.type == pygame.QUIT:
            pygame.quit()
            sys.exit()
        elif e.type == pygame.KEYDOWN:
            if e.key == pygame.K_ESCAPE:  # ESC closes game
                pygame.quit()
                sys.exit()
            elif e.key == pygame.K_f:
                flashlight_on = not flashlight_on
            elif e.key == pygame.K_m:
                minimap_on = not minimap_on

    keys = pygame.key.get_pressed()

    # --- Player Movement ---
    speed = SPEED
    moving = False
    if keys[pygame.K_w]:
        nx, ny = px + math.sin(pa) * speed, py + math.cos(pa) * speed
        if maze_map[int(ny)][int(nx)] != 1:
            px, py = nx, ny
            moving = True
    if keys[pygame.K_s]:
        nx, ny = px - math.sin(pa) * speed, py - math.cos(pa) * speed
        if maze_map[int(ny)][int(nx)] != 1:
            px, py = nx, ny
            moving = True
    if keys[pygame.K_a]:
        pa -= ROT_SPEED
    if keys[pygame.K_d]:
        pa += ROT_SPEED

    # --- Footstep sound ---
    if moving:
        footstep_timer += 1
        if footstep_timer % 10 == 0:
            footstep_sound.play()
    else:
        footstep_timer = 0

    # --- Game updates ---
    if not won and not lost:
        pickup_items()
        update_enemy(dt)
        check_hiding()
        check_vent(keys)
        if math.hypot(enemy["x"] - px, enemy["y"] - py) < 0.5 and not hiding:
            lost = True
        if check_exit():
            won = True

    # --- Rendering ---
    screen.fill((0,0,0))
    cast_rays()
    draw_items()
    draw_enemy()
    draw_vents_3d()
    draw_flashlight()
    draw_message()
    if minimap_on:
        draw_minimap()
    update_vent_fade()
    if won:
        draw_win_screen()
    if lost:
        draw_loss_screen()
    pygame.display.flip()
