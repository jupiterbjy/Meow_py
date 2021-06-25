## Template Image combiner

1. Usage
2. Example 1 & 2
3. Configuration

![image](https://user-images.githubusercontent.com/26041217/122682801-836da500-d236-11eb-8deb-488985c9856b.png)

---

### Usage

Using `template_under.png` and `template_upper.png`, sandwiches user's *profile image* or *attached image*.

```shell
# (Assuming prefix //)

//template [margin_percent=0.0] [background=True]

Attach image to frame it, or user's profile image will be framed. Set margin in percent to add padding.
```

First parameter sets margin percentage. This adds padding to image, or zoom in image when negative value is passed.

Second parameter sets background visibility. If false, will not add `template_under.png` (but still is required) to final image.

---
### Example 1:

- No attachment
- margine -20(zoom 20%)
- background-less
    
![image](https://user-images.githubusercontent.com/26041217/122682569-3fc66b80-d235-11eb-9a27-f2c59c0c2fa4.png)


---
### Example 2:

- Image attached
- margine 10(padding 10%)
- background enabled [Default]

![image](https://user-images.githubusercontent.com/26041217/122682614-7ac89f00-d235-11eb-91cc-ce0418577153.png)

---
### Configuration:

#### Images

- `template_under.png` - layer below user-provided/user-profile layer
- `template_under.png` - layer above user-provided/user-profile layer

**WARNING**: both image should have same width and height.

**DISCLAIMER**: Currently only support square fitting templates.

![image](https://user-images.githubusercontent.com/26041217/123366311-f66a7900-d5b2-11eb-91f9-558afaaaa29f.png)

---

#### config.json

```python
{
    # angle needed to fit in template
    "angle": 3.3,
    
    # file name to look for
    "file_name": ["template_under.png", "template_upper.png"],
    
    # top left corner width, height after rotating
    "bg_offset_after_rotate": [494, 1150],
    
    # length of one side of square after rotation
    "square_height": 1089
}
```

![image](https://user-images.githubusercontent.com/26041217/123368063-10f22180-d5b6-11eb-81b2-7ff50fc8c015.png)
